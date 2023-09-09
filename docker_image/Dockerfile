FROM arm64v8/python:3.9-slim

WORKDIR /app

COPY requirements.txt ./
COPY fast_macd3.4.py ./
COPY start.sh ./
COPY send_email.py ./
COPY PrintAnalyzer.py ./
COPY py_mini_racer-0.6.0-py3-none-linux_aarch64.whl ./

RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
# RUN wget https://gitee.com/fasiondog/hikyuu_extern_libs/releases/download/1.0.0/py_mini_racer-0.6.0-py3-none-linux_aarch64.whl
RUN pip install py_mini_racer-0.6.0-py3-none-linux_aarch64.whl --force-reinstall
RUN apt-get -y update && apt-get -y install cron

# CMD [ "python", "fast_macd3.4.py" ]
CMD [ "sh", "start.sh" ]
