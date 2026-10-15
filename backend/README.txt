中华古建筑知识图谱智能旅游推荐系统——后端

一、文件放置
将main.py、requirements.txt和.env.example复制到项目的backend目录。
将.env.example复制为.env，并填写Neo4j密码。

二、启动命令
进入backend目录后运行：
py -3.14 -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

三、访问地址
接口首页：http://127.0.0.1:8000/
接口文档：http://127.0.0.1:8000/docs
健康检查：http://127.0.0.1:8000/api/health
数据统计：http://127.0.0.1:8000/api/stats

四、主要接口
GET  /api/stats                    图谱数据概览
GET  /api/filters                  检索条件列表
GET  /api/buildings                古建筑组合检索
GET  /api/buildings/{record_id}    古建筑详情
GET  /api/graph/{record_id}        局部知识图谱
GET  /api/recommendations/{id}     可解释旅游推荐
GET  /api/analysis/periods         历史时期统计
POST /api/qa                       自然语言问答

