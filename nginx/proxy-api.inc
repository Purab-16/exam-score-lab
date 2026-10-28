# Shared by every /api location in default.conf: remove the /api prefix and pass the request to the API.

set $api_upstream api:8000;
rewrite ^/api/(.*)$ /$1 break;
proxy_pass http://$api_upstream;

proxy_http_version 1.1;
proxy_set_header Connection "";
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
# Overwritten, not appended, so a client cannot invent its own address. If another proxy or a CDN
# sits in front of nginx, configure the real client address first (see nginx/README.md).
proxy_set_header X-Forwarded-For $remote_addr;
proxy_set_header X-Forwarded-Proto $scheme;

proxy_connect_timeout 5s;
proxy_send_timeout    30s;
proxy_read_timeout    30s;
proxy_hide_header X-Powered-By;

# Only for errors nginx makes itself. The API's own error answers pass through untouched.
error_page 413 = @api_too_large;
error_page 429 = @api_busy;
error_page 502 503 504 = @api_down;
