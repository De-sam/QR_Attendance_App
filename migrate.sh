#!/usr/bin/bash

flask db init
flask db migrate -m "Initial migration."
flask db upgrade
