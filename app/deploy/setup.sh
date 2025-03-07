#!/usr/bin/env bash

set -e

# TODO: Set to URL of git repo.
PROJECT_GIT_URL='https://github.com/Scottman625/Industry_News.git'

PROJECT_BASE_PATH='/usr/local/apps/industry_news'
PROJECT_PATH='/usr/local/apps/industry_news/app'

echo "Installing dependencies..."
apt-get update
apt-get install -y python3-dev python3-venv sqlite python3-pip supervisor nginx git

# 處理已存在的目錄
if [ -d "$PROJECT_BASE_PATH" ]; then
    echo "Directory $PROJECT_BASE_PATH already exists"
    echo "Updating existing repository..."
    cd $PROJECT_BASE_PATH
    
    # 檢查是否為 git 倉庫
    if [ -d ".git" ]; then
        # 獲取遠端分支信息
        git fetch origin
        # 獲取當前分支名稱
        CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD || echo "master")
        echo "Current branch: $CURRENT_BRANCH"
        # 重置到遠端分支的最新狀態
        git reset --hard "origin/$CURRENT_BRANCH"
    else
        echo "Not a git repository. Removing and cloning..."
        cd ..
        rm -rf $PROJECT_BASE_PATH
        git clone $PROJECT_GIT_URL $PROJECT_BASE_PATH
    fi
else
    echo "Creating project directory..."
    mkdir -p $PROJECT_BASE_PATH
    git clone $PROJECT_GIT_URL $PROJECT_BASE_PATH
fi

# 處理虛擬環境
if [ -d "$PROJECT_BASE_PATH/env" ]; then
    echo "Virtual environment already exists"
else
    echo "Creating virtual environment..."
    mkdir -p $PROJECT_BASE_PATH/env
    python3 -m venv $PROJECT_BASE_PATH/env
fi

# 更新 pip
$PROJECT_BASE_PATH/env/bin/python3 -m pip install --upgrade pip

# 安裝 Python 套件
echo "Installing Python packages..."
$PROJECT_BASE_PATH/env/bin/python3 -m pip install -r $PROJECT_BASE_PATH/requirements.txt
$PROJECT_BASE_PATH/env/bin/python3 -m pip install uwsgi

# 執行資料庫遷移和收集靜態文件
echo "Running migrations and collecting static files..."
cd $PROJECT_PATH
$PROJECT_BASE_PATH/env/bin/python3 manage.py migrate
$PROJECT_BASE_PATH/env/bin/python3 manage.py collectstatic --noinput

# 配置 supervisor
echo "Configuring supervisor..."
cp $PROJECT_PATH/deploy/supervisor_profiles_api.conf /etc/supervisor/conf.d/profiles_api.conf
supervisorctl reread
supervisorctl update
supervisorctl restart profiles_api

# 配置 nginx
echo "Configuring nginx..."
cp $PROJECT_PATH/deploy/nginx_profiles_api.conf /etc/nginx/sites-available/profiles_api.conf
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/profiles_api.conf /etc/nginx/sites-enabled/profiles_api.conf
systemctl restart nginx.service

echo "Deployment completed successfully! :)"
