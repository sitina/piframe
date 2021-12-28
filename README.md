# piframe

## Installation
Follow the steps described in https://developers.google.com/photos/library/guides/get-started to get client_secret.json. Then upon the first execution you will get token.pickle and with that the application will be able to run.

https://github.com/ido-ran/google-photos-api-python-quickstart/blob/master/quickstart.py

## service
Copy piframe.service to /etc/systemd/system/piframe.service

sudo systemctl start piframe
sudo systemctl status piframe

sudo systemctl restart piframe
sudo systemctl status piframe

sudo systemctl enable piframe
