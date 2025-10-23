from celery import Celery
celery_app = Celery(
    'tasks',
    broker='redis://127.0.0.1:6379/0',  # Redis作为消息代理
    backend='redis://127.0.0.1:6379/1'  # 使用Redis存储任务结果
)
celery_app.config_from_object('API_APP.celery_config')

#  首先到redis目录启动redis，命令：redis-server.exe redis.windows.conf
#  celery任务界面查看：celery --broker="redis://127.0.0.1:6379/0" flower
#  启动命令(windows)：celery -A API_APP.celery_app:celery_app worker -P gevent --loglevel=info
#  启动命令：celery -A API_APP.celery_app:celery_app worker --loglevel=info

#  celery调试命令：celery -A API_APP.celery_app:celery_app worker -P gevent --loglevel=debug
