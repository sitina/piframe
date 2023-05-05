# piframe

As we have an old IPad with no chance of further updates we have decided to think about the option of turning it to the photoframe. As even this ancient IPad runs safari, the server app running somewhere came to my mind.

The application that serves the photos from google photos album can run even on raspberry pi and this is exactly the case.

## Installation

* Clone the repository to your raspberry (in my case it is located in /home/pi/piframe).

* Install python3 and also make sure you have virtualenv and pip3 available

* Run `./start-install.sh` to initiate the virtual environment (the application should be running on the ip address of your raspberry and port 81 - see the output of the application in the console for the exact address).

* Follow the steps described in https://developers.google.com/photos/library/guides/get-started to get client_secret.json. Then upon the first execution you will get token.pickle and with that the application will be able to run (https://github.com/ido-ran/google-photos-api-python-quickstart/blob/master/quickstart.py).

* Once the virtualenv is ready/initialised, you can run the app only using `./start.sh`

* The app will fetch the first google album from the available ones during the initial run, then stores it in `config.json` file (where it is easy to specify your own)

* The app is available on the address of RPI and port 81 (see `start.sh`/`start-install.sh` for the config options to setup the custom port)

## Run the piserver as a service
Copy piframe.service to /etc/systemd/system/piframe.service

`sudo systemctl start piframe`
`sudo systemctl status piframe`

`sudo systemctl restart piframe`
`sudo systemctl status piframe`

`sudo systemctl enable piframe`
