from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import requests
import json
import logging
from .models import ESPDevice, SortingSession, Tomato
from .tomato_detector import TomatoDetector

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize the tomato detector
tomato_detector = None

def home(request):
    device = ESPDevice.get_default_device()
    active_session = SortingSession.objects.filter(is_active=True).first()

    # Get device status if IP is available
    device_status = {
        'online': False,
        'ip': device.ip_address or 'Not set',
        'ripe_count': 0,
        'green_count': 0,
        'running': False
    }

    if device.ip_address:
        try:
            response = requests.get(f"http://{device.ip_address}/status", timeout=2)
            if response.status_code == 200:
                data = response.json()
                device_status['online'] = True
                device_status['running'] = data.get('running', False)
                device_status['ripe_count'] = data.get('ripe_count', 0)
                device_status['green_count'] = data.get('green_count', 0)

                # Update device status
                device.is_online = True
                device.save()
        except:
            device.is_online = False
            device.save()

    # Get session statistics
    sessions = SortingSession.objects.order_by('-start_time')[:5]

    context = {
        'device': device,
        'device_status': device_status,
        'active_session': active_session,
        'sessions': sessions,
    }

    return render(request, 'home.html', context)

@csrf_exempt
def update_device_ip(request):
    if request.method == 'POST':
        ip_address = request.POST.get('ip_address')
        if ip_address:
            device = ESPDevice.get_default_device()
            device.ip_address = ip_address
            device.save()

            # Test connection
            try:
                response = requests.get(f"http://{ip_address}/status", timeout=2)
                if response.status_code == 200:
                    device.is_online = True
                    device.save()
                    return JsonResponse({'status': 'success', 'message': 'Connected successfully'})
            except:
                pass

            return JsonResponse({'status': 'warning', 'message': 'IP updated but connection failed'})

        return JsonResponse({'status': 'error', 'message': 'Invalid IP address'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@csrf_exempt
def control_device(request):
    if request.method == 'POST':
        command = request.POST.get('command')
        device = ESPDevice.get_default_device()

        if not device.ip_address or not device.is_online:
            return JsonResponse({'status': 'error', 'message': 'Device is offline or IP not set'})

        if command in ['stop', 'release', 'sort_neutral', 'reset_counts']:
            try:
                payload = {'command': command}
                response = requests.post(
                    f"http://{device.ip_address}/control",
                    json=payload,
                    timeout=2
                )

                if response.status_code == 200:
                    # Handle session management
                    if command == 'release':
                        # Start a new session if none is active
                        active_session = SortingSession.objects.filter(is_active=True).first()
                        if not active_session:
                            SortingSession.objects.create(device=device)
                    elif command == 'stop':
                        # End active session
                        active_session = SortingSession.objects.filter(is_active=True).first()
                        if active_session:
                            active_session.end_session()

                    return JsonResponse({'status': 'success', 'message': f'Command {command} sent successfully'})

                return JsonResponse({'status': 'error', 'message': 'Failed to send command'})
            except:
                device.is_online = False
                device.save()
                return JsonResponse({'status': 'error', 'message': 'Device connection failed'})

        return JsonResponse({'status': 'error', 'message': 'Invalid command'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@csrf_exempt
def sort_tomato(request):
    if request.method == 'POST':
        tomato_type = request.POST.get('type')
        from_camera = request.POST.get('from_camera') == 'true'
        device = ESPDevice.get_default_device()

        if not device.ip_address or not device.is_online:
            return JsonResponse({'status': 'error', 'message': 'Device is offline or IP not set'})

        if tomato_type in ['ripe', 'green']:
            try:
                # Get or create active session
                active_session = SortingSession.objects.filter(is_active=True).first()
                if not active_session:
                    active_session = SortingSession.objects.create(device=device)

                # Record the tomato with source information
                tomato = Tomato.objects.create(
                    session=active_session,
                    is_ripe=(tomato_type == 'ripe')
                )

                # Add detection source to the payload
                payload = {
                    'type': tomato_type,
                    'from_camera': from_camera
                }

                # Send command to ESP
                response = requests.post(
                    f"http://{device.ip_address}/sort",
                    json=payload,
                    timeout=2
                )

                if response.status_code == 200:
                    # Parse the response from ESP32
                    try:
                        esp_data = response.json()
                        return JsonResponse({
                            'status': 'success',
                            'message': f'Sorted {tomato_type} tomato',
                            'from_camera': from_camera,
                            'ripe_count': esp_data.get('ripe_count', active_session.ripe_count),
                            'green_count': esp_data.get('green_count', active_session.green_count),
                            'camera_ripe_count': esp_data.get('camera_ripe_count', 0),
                            'camera_green_count': esp_data.get('camera_green_count', 0)
                        })
                    except:
                        # Fallback if ESP32 doesn't return JSON
                        return JsonResponse({
                            'status': 'success',
                            'message': f'Sorted {tomato_type} tomato',
                            'from_camera': from_camera,
                            'ripe_count': active_session.ripe_count,
                            'green_count': active_session.green_count
                        })

                return JsonResponse({'status': 'error', 'message': 'Failed to send command'})
            except Exception as e:
                logger.error(f"Error in sort_tomato: {str(e)}")
                return JsonResponse({'status': 'error', 'message': f'Error: {str(e)}'})

        return JsonResponse({'status': 'error', 'message': 'Invalid tomato type'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@csrf_exempt
def get_status(request):
    device = ESPDevice.get_default_device()
    active_session = SortingSession.objects.filter(is_active=True).first()

    status = {
        'device_online': device.is_online,
        'device_ip': device.ip_address,
        'session_active': active_session is not None,
        'webcam_config': {
            'enabled': device.webcam_enabled,
            'use_webcam': device.use_webcam,
            'detection_mode': device.detection_mode,
            'detection_sensitivity': device.detection_sensitivity,
            'ripe_threshold_min': device.ripe_threshold_min,
            'ripe_threshold_max': device.ripe_threshold_max,
            'green_threshold_min': device.green_threshold_min,
            'green_threshold_max': device.green_threshold_max
        }
    }

    if active_session:
        status.update({
            'session_id': active_session.id,
            'session_start': active_session.start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'session_duration': int(active_session.duration),
            'ripe_count': active_session.ripe_count,
            'green_count': active_session.green_count,
            'total_count': active_session.total_tomatoes
        })

    # Try to get ESP status
    esp_status = {}
    if device.ip_address and device.is_online:
        try:
            response = requests.get(f"http://{device.ip_address}/status", timeout=2)
            if response.status_code == 200:
                esp_status = response.json()
        except:
            device.is_online = False
            device.save()

    status['esp_status'] = esp_status

    return JsonResponse(status)

@csrf_exempt
def update_webcam_config(request):
    if request.method == 'POST':
        device = ESPDevice.get_default_device()

        # Update webcam settings
        if 'webcam_enabled' in request.POST:
            device.webcam_enabled = request.POST.get('webcam_enabled') == 'true'

        if 'detection_mode' in request.POST:
            mode = request.POST.get('detection_mode')
            if mode in [m[0] for m in ESPDevice.DETECTION_MODES]:
                device.detection_mode = mode

        if 'detection_sensitivity' in request.POST:
            try:
                sensitivity = int(request.POST.get('detection_sensitivity'))
                device.detection_sensitivity = max(0, min(100, sensitivity))
            except ValueError:
                pass

        if 'ripe_threshold_min' in request.POST and 'ripe_threshold_max' in request.POST:
            try:
                min_val = int(request.POST.get('ripe_threshold_min'))
                max_val = int(request.POST.get('ripe_threshold_max'))
                device.ripe_threshold_min = min_val
                device.ripe_threshold_max = max_val
            except ValueError:
                pass

        if 'green_threshold_min' in request.POST and 'green_threshold_max' in request.POST:
            try:
                min_val = int(request.POST.get('green_threshold_min'))
                max_val = int(request.POST.get('green_threshold_max'))
                device.green_threshold_min = min_val
                device.green_threshold_max = max_val
            except ValueError:
                pass

        device.save()

        return JsonResponse({
            'status': 'success',
            'message': 'Webcam configuration updated',
            'config': {
                'enabled': device.webcam_enabled,
                'detection_mode': device.detection_mode,
                'detection_sensitivity': device.detection_sensitivity,
                'ripe_threshold_min': device.ripe_threshold_min,
                'ripe_threshold_max': device.ripe_threshold_max,
                'green_threshold_min': device.green_threshold_min,
                'green_threshold_max': device.green_threshold_max
            }
        })

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@csrf_exempt
def detect_tomato(request):
    """
    API endpoint for detecting tomatoes in an image.
    Expects a base64 encoded image in the request body.
    """
    if request.method == 'POST':
        global tomato_detector

        # Get device configuration
        device = ESPDevice.get_default_device()

        # Initialize or update detector with current config
        config = {
            'ripe_threshold_min': device.ripe_threshold_min,
            'ripe_threshold_max': device.ripe_threshold_max,
            'green_threshold_min': device.green_threshold_min,
            'green_threshold_max': device.green_threshold_max,
            'detection_sensitivity': device.detection_sensitivity
        }

        if tomato_detector is None:
            tomato_detector = TomatoDetector(config)
        else:
            tomato_detector.update_config(config)

        try:
            # Get base64 image from request
            data = json.loads(request.body)
            base64_image = data.get('image')

            if not base64_image:
                return JsonResponse({'status': 'error', 'message': 'No image provided'})

            # Process the image
            result = tomato_detector.detect_from_base64(base64_image)

            if 'error' in result:
                return JsonResponse({'status': 'error', 'message': result['error']})

            # Return detection results
            return JsonResponse({
                'status': 'success',
                'detection': {
                    'type': result.get('type'),
                    'confidence': round(result.get('confidence', 0), 1),
                    'contours': result.get('contours', 0)
                }
            })

        except Exception as e:
            logger.error(f"Error in detect_tomato: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})