# AWS Deployment Guide for School Management System

This guide will walk you through deploying the School Management System on AWS.

## Prerequisites

1. AWS Account
2. Domain name (optional but recommended)
3. SSH key pair for EC2 access

## 1. Set Up AWS Infrastructure

### 1.1 Launch an EC2 Instance
- Launch an EC2 instance (Ubuntu 22.04 LTS recommended)
- Minimum requirements: t2.micro (free tier eligible)
- Recommended: t3.small or larger for production
- Security Group Rules:
  - SSH (port 22) - Your IP only
  - HTTP (port 80) - 0.0.0.0/0
  - HTTPS (port 443) - 0.0.0.0/0
  - Custom TCP (port 8000) - 127.0.0.1/32 (for Gunicorn)

### 1.2 Set Up RDS Database
- Launch an RDS PostgreSQL instance
- Choose appropriate size (db.t3.micro for testing)
- Enable Multi-AZ for production
- Set up security group to allow access from EC2 security group
- Note down database credentials

### 1.3 Set Up S3 Bucket (Optional, for media files)
- Create an S3 bucket
- Enable static website hosting
- Set up CORS configuration
- Create an IAM user with S3 access

## 2. Server Setup

### 2.1 Connect to Your EC2 Instance
```bash
ssh -i your-key.pem ubuntu@your-ec2-public-ip
```

### 2.2 Install Dependencies
```bash
# Update package list
sudo apt update

# Install system dependencies
sudo apt install -y python3-pip python3-dev python3-venv libpq-dev postgresql postgresql-contrib nginx git

# Install Node.js (if needed for frontend assets)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

### 2.3 Set Up Virtual Environment
```bash
# Create project directory
mkdir -p /opt/school_management
cd /opt/school_management

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 2.4 Configure Environment Variables
```bash
# Create .env file
nano .env
```

Copy the contents from `.env.example` and update with your actual values.

## 3. Database Setup

### 3.1 Create Database and User
```bash
sudo -u postgres psql
CREATE DATABASE schooldb;
CREATE USER schooluser WITH PASSWORD 'yourpassword';
ALTER ROLE schooluser SET client_encoding TO 'utf8';
ALTER ROLE schooluser SET default_transaction_isolation TO 'read committed';
ALTER ROLE schooluser SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE schooldb TO schooluser;
\q
```

### 3.2 Run Migrations
```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

## 4. Set Up Gunicorn

### 4.1 Create Gunicorn Service
```bash
sudo nano /etc/systemd/system/gunicorn.service
```

Add the following content:
```ini
[Unit]
Description=gunicorn daemon
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/opt/school_management
ExecStart=/opt/school_management/venv/bin/gunicorn --access-logfile - --workers 3 --bind unix:/opt/school_management/school_management.sock Analitica.wsgi:application

[Install]
WantedBy=multi-user.target
```

### 4.2 Start and Enable Gunicorn
```bash
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
```

## 5. Configure Nginx

### 5.1 Create Nginx Configuration
```bash
sudo nano /etc/nginx/sites-available/school_management
```

Add the following configuration:
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        root /opt/school_management;
    }
    
    location /media/ {
        root /opt/school_management;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/opt/school_management/school_management.sock;
    }
}
```

### 5.2 Enable the Site
```bash
sudo ln -s /etc/nginx/sites-available/school_management /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

## 6. Set Up SSL with Let's Encrypt

### 6.1 Install Certbot
```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 6.2 Obtain SSL Certificate
```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

### 6.3 Set Up Auto-Renewal
```bash
sudo certbot renew --dry-run
```

## 7. Final Steps

1. Update your domain's DNS settings to point to your EC2 instance's public IP
2. Test your site at https://yourdomain.com
3. Access the admin panel at https://yourdomain.com/admin/

## Maintenance

### Update the Application
```bash
cd /opt/school_management
git pull
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn
```

### View Logs
```bash
# Gunicorn logs
sudo journalctl -u gunicorn

# Nginx error logs
sudo tail -f /var/log/nginx/error.log
```
