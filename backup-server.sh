echo 'stopping minecraft service'
sudo systemctl stop minecraft.service

echo 'sync server with aws s3'
date=$(date '+%Y-%m-%d-%H-%M-%S')
sudo aws s3 sync /opt/minecraft/server s3://mine-bucket-aparecido/$date

echo 'starting minecraft service'
sudo systemctl start minecraft.service