@echo off
chcp 65001 >nul
title 网球赛事智能编排系统
echo ========================================
echo      🎾 网球赛事智能编排系统 启动中...
echo ========================================
cd /d "%~dp0"

:: 检查前端是否已经打包
if not exist "frontend\dist\index.html" (
    echo [提示] 检测到首次运行，正在为您编译前端界面，请耐心等待1-2分钟...
    cd frontend
    call npm install
    call npm run build
    cd ..
    echo [成功] 前端编译完成！
)

echo.
echo 正在拉起可视化界面，请勿关闭此黑窗口...
python app.py