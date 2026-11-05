@echo off
cd /d C:\Dev\rbgg\api\scripts
start /B python train_twilight_ppo.py --timesteps 500000 --resume C:\Dev\rbgg\runtime\twilight-ppo-v3-opponents\twilight-ppo-v3_8192.zip --opponents "rule=0.3,random=0.3,snapshot=0.4" --curriculum auto --curriculum-threshold 0.50 --curriculum-min-timesteps 50000 --max-episode-steps 3000 --output C:\Dev\rbgg\runtime\twilight-ppo-v4 --checkpoint-frequency 50000 --n-envs 4 > _train_twilight_ppo.log 2>&1
