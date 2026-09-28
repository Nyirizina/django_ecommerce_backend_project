#!/bin/bash
# Vercel build script – run during the build phase
pip install -r requirements.txt
python manage.py collectstatic --noinput
