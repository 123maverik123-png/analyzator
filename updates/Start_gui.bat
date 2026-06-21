@echo off
chcp 65001 >nul
cd /d "%~dp0"

set VENV_DIR=venv
set REQUIREMENTS=requirements.txt

echo ============================================
echo  Анализатор разговоров — запуск
echo ============================================

:: Проверяем, существует ли виртуальное окружение
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Виртуальное окружение не найдено. Создаю...
    python -m venv %VENV_DIR%
    if errorlevel 1 (
        echo Ошибка при создании виртуального окружения.
        echo Убедитесь, что Python установлен и добавлен в PATH.
        pause
        exit /b 1
    )
    echo Виртуальное окружение создано.
)

:: Устанавливаем зависимости, если requirements.txt есть
if exist %REQUIREMENTS% (
    echo Проверяю установленные пакеты...
    "%VENV_DIR%\Scripts\python.exe" -c "import sv_ttk, vlc, requests" 2>nul
    if errorlevel 1 (
        echo Устанавливаю зависимости из %REQUIREMENTS%...
        "%VENV_DIR%\Scripts\pip.exe" install -r %REQUIREMENTS%
        if errorlevel 1 (
            echo Ошибка при установке зависимостей.
            echo Проверьте интернет-соединение и файл %REQUIREMENTS%.
            pause
            exit /b 1
        )
        echo Зависимости успешно установлены.
    ) else (
        echo Все необходимые модули уже установлены.
    )
) else (
    echo Файл %REQUIREMENTS% не найден. Пропускаю установку.
)

:: Запускаем GUI
echo Запуск приложения...
start "" "%VENV_DIR%\Scripts\pythonw.exe" gui.py

exit