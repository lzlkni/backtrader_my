#coding:utf-8
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class SendEmail:
    global send_user
    global email_host
    global password
    password = "ylnclfzmrzjpbbbi"
    email_host = "smtp.qq.com"
    send_user = "lzl_kni@qq.com"

    def send_mail(self, user_list, sub, content, attch=None):
        user = send_user
        
        message = MIMEMultipart()
        message['Subject'] = sub
        message['From'] = user
        message['To'] = ";".join(user_list)

          # 邮件正文内容
        message.attach(MIMEText(content, 'plain', 'utf-8'))
        
        if attch:
            # 构造附件（附件为txt格式的文本）
            att = MIMEText(open(attch, 'rb').read(), 'base64', 'utf-8')
            att["Content-Type"] = 'application/octet-stream'
            att["Content-Disposition"] = 'attachment; filename="result.csv"'
            message.attach(att)


        server = smtplib.SMTP_SSL(email_host.encode(), 465)
        # server.connect(email_host,465)
        server.login(send_user,password)
        server.sendmail(user,user_list,message.as_string())
        server.close()

if __name__ == '__main__':
    send = SendEmail()
    user_list = ['lzl_kni@qq.com']
    sub = "测试邮件"
    content = "testing"
    attch = 'result.csv'

    send.send_mail(user_list,sub,content, attch)