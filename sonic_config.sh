sshpass -p 'admin' scp configs/fabric/startup-multi_dc_fabric/sonic/config_db.json admin@leaf5:/tmp/config_db.json
sshpass -p 'admin' ssh admin@leaf5 "echo admin | sudo -S mv /tmp/config_db.json /etc/sonic/config_db.json && sudo config reload -y"
