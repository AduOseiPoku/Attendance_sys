# Hosting Django on Oracle Cloud Infrastructure (OCI) with Gunicorn & Nginx

This guide walks you through the complete process of hosting your Django project on an OCI Ubuntu instance and making it accessible to the internet.

---

## Phase 1: OCI Network Permissions (Security Lists)

Oracle Cloud Infrastructure blocks all incoming traffic by default unless explicitly permitted in your Virtual Cloud Network (VCN).

1. Log in to the **Oracle Cloud Console**.
2. Navigate to **Networking** > **Virtual Cloud Networks**.
3. Select the VCN associated with your instance.
4. Under **Resources** (left sidebar), click on **Security Lists** and select your **Default Security List** (or the specific list for your public subnet).
5. Click **Add Ingress Rules** and add rules to allow HTTP and HTTPS traffic:

| Source Type | Source CIDR | IP Protocol | Source Port Range | Destination Port Range | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CIDR** | `0.0.0.0/0` | TCP | All | `80` | Allow HTTP traffic |
| **CIDR** | `0.0.0.0/0` | TCP | All | `443` | Allow HTTPS traffic |

---

## Phase 2: Host Operating System Firewall (Ubuntu iptables)

OCI Ubuntu instances use `iptables` by default, which blocks most incoming ports even if you allow them in the OCI Security Lists. You must open them on the instance itself.

Once you SSH into your instance (`ssh -i <your-key> ubuntu@152.70.26.21`), run the following commands:

```bash
# Allow HTTP and HTTPS traffic through the firewall
sudo iptables -I INPUT 6 -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -p tcp --dport 443 -j ACCEPT

# Save the iptables rules so they persist after reboot
sudo netfilter-persistent save
```

---

## Phase 3: Project Setup on the Instance

1. **Update and Install System Dependencies**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install python3-pip python3-venv python3-dev libpq-dev nginx curl git -y
   ```

2. **Clone/Transfer your Django project**:
   Navigate to `/var/www/` or your user home directory:
   ```bash
   cd /var/www
   sudo chown -R ubuntu:ubuntu /var/www
   git clone <your-repository-url> attendance_sys
   cd attendance_sys
   ```

3. **Set Up Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   pip install gunicorn psycopg2-binary
   ```

4. **Update `core/settings.py`**:
   Ensure that the server's public IP address (`152.70.26.21`) or your domain is included in `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`:
   ```python
   ALLOWED_HOSTS = ['152.70.26.21', 'localhost', '127.0.0.1']
   CSRF_TRUSTED_ORIGINS = ['http://152.70.26.21']
   ```

5. **Run Migrations and Collect Static Files**:
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```

---

## Phase 4: Configure Gunicorn as a Service

Creating a systemd service allows Gunicorn to start automatically when the server boots and restart if it crashes.

1. **Create the Gunicorn Socket File**:
   ```bash
   sudo nano /etc/systemd/system/gunicorn.socket
   ```
   Add the following content:
   ```ini
   [Unit]
   Description=gunicorn socket

   [Socket]
   ListenStream=/run/gunicorn.sock

   [Install]
   WantedBy=sockets.target
   ```

2. **Create the Gunicorn Service File**:
   ```bash
   sudo nano /etc/systemd/system/gunicorn.service
   ```
   Add the following content (adjust paths if your project directory structure varies):
   ```ini
   [Unit]
   Description=gunicorn daemon
   Requires=gunicorn.socket
   After=network.target

   [Service]
   User=ubuntu
   Group=www-data
   WorkingDirectory=/var/www/attendance_sys
   ExecStart=/var/www/attendance_sys/venv/bin/gunicorn \
             --access-logfile - \
             --workers 3 \
             --bind unix:/run/gunicorn.sock \
             core.wsgi:application

   [Install]
   WantedBy=multi-user.target
   ```

3. **Start and Enable Gunicorn**:
   ```bash
   sudo systemctl start gunicorn.socket
   sudo systemctl enable gunicorn.socket
   ```

---

## Phase 5: Configure Nginx as a Reverse Proxy

Nginx will receive public requests on port 80 and route them to Gunicorn via the Unix socket.

1. **Create an Nginx Configuration File**:
   ```bash
   sudo nano /etc/nginx/sites-available/attendance_sys
   ```
   Add the following content:
   ```nginx
   server {
       listen 80;
       server_name 152.70.26.21;

       location = /favicon.ico { access_log off; log_not_found off; }
       
       # Path to Django project static files
       location /static/ {
           root /var/www/attendance_sys;
       }

       # Route all other traffic to Gunicorn socket
       location / {
           include proxy_params;
           proxy_pass http://unix:/run/gunicorn.sock;
       }
   }
   ```

2. **Enable the Configuration and Restart Nginx**:
   ```bash
   sudo ln -s /etc/nginx/sites-available/attendance_sys /etc/nginx/sites-enabled/
   sudo nginx -t  # Tests configuration syntax
   sudo systemctl restart nginx
   ```

---

## Phase 6: Accessing Your Web App

Once the configuration is complete, your application will be available at:
`http://152.70.26.21`

If you encounter issues, check the service logs:
```bash
# Check Gunicorn status and logs
sudo systemctl status gunicorn
sudo journalctl -u gunicorn --no-pager -n 50

# Check Nginx logs
sudo tail -n 50 /var/log/nginx/error.log
```
