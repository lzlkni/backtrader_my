#!/bin/bash
# start cron
service cron start

# create cron job
# echo '* * * * * root echo "Hello World at $(date)" >> /var/log/greeting.txt' > /etc/cron.d/hello-cron
# echo '30 15 * * 1-5 root python /app/fast_macd3.4.py && echo "macd run at $(date)" >> var/log/greeting.txt' > /etc/cron.d/hello-cron
# echo '0 9 * * 1-5 root /usr/local/bin/python /app/fast_macd3.4.py >> var/log/greeting.txt' > /etc/cron.d/hello-cron
echo '0 9 * * 1-5 root /usr/local/bin/python /app/fast_macd3.4.py >> /var/log/macd.log 2>&1' > /etc/cron.d/macd-run1
echo '30 15 * * 1-5 root /usr/local/bin/python /app/fast_macd3.4.py >> /var/log/macd.log 2>&1' > /etc/cron.d/macd-run2
# echo '* * * * * root /usr/local/bin/python /app/fast_macd3.4.py >> /var/log/macd.log 2>&1' > /etc/cron.d/hello-cron

# ensure cron is running
service cron status

ls -l /etc/cron.d
# python3 /app/fast_macd3.4.py >> /var/log/macd.log 2>&1

while [ ! -f /var/log/macd.log ]
do
    echo "waitting file..."
    sleep 10
done

tail -f /var/log/macd.log
