[app]
title = Cham Thi Trac Nghiem
package.name = chamthitracnghiem
package.domain = org.thptgrading

source.dir = .
source.include_exts = py,png,jpg,jpeg,json,ttf

version = 0.1.0

requirements = python3,kivy,pillow,openpyxl,plyer,qrcode

orientation = portrait
fullscreen = 0

icon.filename = %(source.dir)s/icon.png

android.permissions = CAMERA,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,INTERNET

android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1
