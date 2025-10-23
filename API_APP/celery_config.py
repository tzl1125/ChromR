import os

from celery import states
from celery.result import AsyncResult
from celery.signals import task_postrun

from API_APP.Fp_growth import fp_growth
from API_APP.celery_app import celery_app
from API_APP.data_manager import get_frontend_data, save_frontend_data
from API_APP.design_space import includeN, withM, withoutM, includeN_noR, withM_noR, withoutM_noR
from API_APP.multi_optimization import multi_opt_cal


@task_postrun.connect
def update_task_status(task_id=None, state=None, **kwargs):
    task_result = AsyncResult(task_id, app=celery_app)
    actual_result = task_result.result
    data = get_frontend_data()
    updated = False
    for task in data.tasks:
        if task.id == task_id:
            if state == states.SUCCESS:
                task.status = "已完成"
                task.result = actual_result if isinstance(actual_result, str) else str(actual_result)
            elif state == states.FAILURE:
                task.status = "失败"
                task.result = getattr(actual_result, "args", ["未知错误"])[0]
            else:
                task.status = state
            updated = True
            break
    if updated:
        save_frontend_data(data)
        print(f"任务 {task_id} 状态已更新并保存至 Redis")
    else:
        print(f"警告：未找到任务 {task_id}，更新失败")


@celery_app.task(bind=True)
def cal_fg_task(self, data_path, current_dir, min_support, min_conf):
    try:
        file_name = fp_growth.calculation(data_path, current_dir, min_support, min_conf, self.request.id)
        os.remove(data_path)
        return file_name
    except Exception as e:
        self.update_state(
            state=states.FAILURE,
            meta={
                "exc_type": type(e).__name__,
                "exc_message": str(e)
            }
        )
        raise e


@celery_app.task(bind=True)
def cal_design_space_task(self, data_paths, cal_para, current_dir, ds_type):
    try:
        file_name = None
        # 处理带概率的设计空间计算
        if ds_type in ["includeN", "withM", "withoutM"]:
            mt, p, r = cal_para
            if ds_type == "includeN":
                file_name = includeN.main(data_paths["YLimits"], data_paths["ParameterCondition"],
                                          data_paths["ExpResults"],
                                          data_paths["XLimitsSteps"], mt, r, p, current_dir, self.request.id)
            elif ds_type == "withM":
                file_name = withM.main(data_paths["YLimits"], data_paths["ParameterCondition"],
                                       data_paths["MaterialCondition"], data_paths["ExpResults"],
                                       data_paths["XLimitsSteps"], mt, r, p, current_dir, self.request.id)
            elif ds_type == "withoutM":
                file_name = withoutM.main(data_paths["YLimits"], data_paths["ParameterCondition"],
                                          data_paths["ExpResults"],
                                          data_paths["XLimitsSteps"], mt, r, p, current_dir, self.request.id)

        # 处理无概率的设计空间计算
        elif ds_type in ["includeN-noR", "withM-noR", "withoutM-noR"]:
            p = cal_para[0]
            if ds_type == "includeN-noR":
                file_name = includeN_noR.main(data_paths["YLimits"], data_paths["ParameterCondition"],
                                              data_paths["ExpResults"], data_paths["XLimitsSteps"],
                                              p, current_dir, self.request.id)
            elif ds_type == "withM-noR":
                file_name = withM_noR.main(data_paths["YLimits"], data_paths["ParameterCondition"],
                                           data_paths["MaterialCondition"], data_paths["ExpResults"],
                                           data_paths["XLimitsSteps"], p, current_dir, self.request.id)
            elif ds_type == "withoutM-noR":
                file_name = withoutM_noR.main(data_paths["YLimits"], data_paths["ParameterCondition"],
                                              data_paths["ExpResults"], data_paths["XLimitsSteps"],
                                              p, current_dir, self.request.id)

        for data_path in data_paths.values():
            os.remove(data_path)
        return file_name
    except Exception as e:
        self.update_state(
            state=states.FAILURE,
            meta={
                "exc_type": type(e).__name__,
                "exc_message": str(e)
            }
        )
        raise e


@celery_app.task(bind=True)
def cal_multi_opt_task(self, request, current_dir):
    try:
        file_name = multi_opt_cal.calculation(request, current_dir, self.request.id)
        return file_name
    except Exception as e:
        self.update_state(
            state=states.FAILURE,
            meta={
                "exc_type": type(e).__name__,
                "exc_message": str(e)
            }
        )
        raise e
