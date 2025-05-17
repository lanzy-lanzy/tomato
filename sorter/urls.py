from django.urls import path
from .views import home, update_device_ip, control_device, sort_tomato, get_status, update_webcam_config, detect_tomato

urlpatterns = [
    path('', home, name='home'),
    path('api/update-ip/', update_device_ip, name='update_ip'),
    path('api/control/', control_device, name='control_device'),
    path('api/sort/', sort_tomato, name='sort_tomato'),
    path('api/status/', get_status, name='get_status'),
    path('api/webcam-config/', update_webcam_config, name='update_webcam_config'),
    path('api/detect/', detect_tomato, name='detect_tomato'),
]
