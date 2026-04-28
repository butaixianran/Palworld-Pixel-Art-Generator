pyinstaller src/main.py --icon=src/app.ico --noconfirm ^
  --add-data "src/i18n/en.json;i18n" ^
  --add-data "src/i18n/zh_CN.json;i18n" ^
  --add-data "src/i18n/ja.json;i18n"
  
pause