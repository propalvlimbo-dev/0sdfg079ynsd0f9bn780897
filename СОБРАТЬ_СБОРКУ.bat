@echo off
chcp 65001 >nul
echo ===================================================
echo   Elytrix 1.21 - Сборка архива плагинов
echo ===================================================
if not exist "Elytrix-1.21-Plugins.zip.001" (
    echo [ОШИБКА] Не найден файл Elytrix-1.21-Plugins.zip.001 в этой папке!
    pause
    exit /b 1
)
if not exist "Elytrix-1.21-Plugins.zip.002" (
    echo [ОШИБКА] Не найден файл Elytrix-1.21-Plugins.zip.002 в этой папке!
    pause
    exit /b 1
)
copy /b "Elytrix-1.21-Plugins.zip.001"+"Elytrix-1.21-Plugins.zip.002" "Elytrix-1.21-Plugins.zip" >nul
echo [ГОТОВО] Архив Elytrix-1.21-Plugins.zip успешно собран!
echo Теперь распакуйте Elytrix-1.21-Plugins.zip на ваш сервер.
pause
