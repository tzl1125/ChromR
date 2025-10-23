# ChromR  
A Chromatographic Process Design and Optimization Platform Powered by Large Language Models  


This work presents ChromR, a large language model (LLM)-driven platform for chromatographic process design and optimization. The platform integrates ChromLLM, a LLM specifically trained for the chromatography domain, and consists of a multi-agent system and an automated chromatographic experimental device. The multi-agent system comprises four functional agents (domain knowledge answering, experimental design, experimental execution, and data analysis). ChromR can automatically complete the entire workflow from initial process parameter recommendation, experimental design, automated execution to data analysis and multi-objective optimization. It effectively reduces reliance on expert experience while significantly cutting down manual labor and process development time.  


## Project File Description  
- **API_APP**: The backend program of ChromR, built on the high-performance FastAPI framework. It mainly handles the tool interaction logic of the multi-agent system in ChromR.  
- **chromR_frontend**: The frontend program of ChromR, developed using Vue3.js and Node.js frameworks. It is responsible for the web frontend interface display of ChromR.  
- **dify_component**: It contains dify configuration files for the multi-agent system, including the integrated ChromR and four individual agents.  
- **hardware_server**: The control code for ChromR's automated chromatographic experimental device, based on the high-performance FastAPI framework. It primarily handles logic related to automated chromatographic operations and device unit control.  
- **mysql**: It includes code for connecting to the MySQL database used by ChromR.  


## License  
ChromR is distributed under an Apache-2.0 license
