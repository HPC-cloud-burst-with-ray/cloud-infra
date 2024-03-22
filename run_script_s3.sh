#!/bin/bash
# Set the counter to 0
counter=0

while [ $counter -lt 7 ]; do
  # Run the command
  echo "Start Image Processing"
  # python3 -u image_processing_s3.py 200
  # sleep 10
  # python3 -u image_processing_s3.py 150
  # # sleep 10
  # python3 -u image_processing_s3.py 100

  python3 -u image_processing_s3.py 80
  # sleep 10
  # python3 -u image_processing_s3.py 50
  # # sleep 10
  # python3 -u image_processing_s3.py 30
  # # sleep 10
  echo "Image Processing Done"
  
  echo "Start ML tuning"
  # python3 -u ml_tuning_s3.py 200
  # sleep 10
  # python3 -u ml_tuning_s3.py 150
  # # sleep 10
  # python3 -u ml_tuning_s3.py 100

  python3 -u ml_tuning_s3.py 80
  # sleep 10
  # python3 -u ml_tuning_s3.py 50
  # # sleep 10
  # python3 -u ml_tuning_s3.py 30
  # sleep 10
  echo "ML tuning Done"

  # Increment the counter
  ((counter++))
done
# while ; do
#   timeout 120m python3 -u ml_tuning_s3.py 200 >> output.txt 2>&1
#   sleep 10
#   # timeout 120m python3 -u ml_tuning_s3.py 150 >> output.txt 2>&1
#   # sleep 10
#   # timeout 120m python3 -u ml_tuning_s3.py 100 >> output.txt 2>&1
#   # sleep 10
#   # timeout 120m python3 -u ml_tuning_s3.py 50 >> output.txt 2>&1
#   # sleep 10
# done
