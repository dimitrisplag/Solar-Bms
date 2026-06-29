import os
import json
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django import forms
from django.contrib.auth.decorators import login_required

# Εισάγουμε τα μοντέλα που φτιάξαμε για το IoT
from .models import Device, Measurement 
from django.core.mail import send_mail
from django.core.cache import cache

@login_required
def home(request):
    selected_device_mac= request.GET.get('device')
    
    if request.user.is_superuser and not selected_device_mac:
        return redirect('fleet_dashboard')
    
    if request.user.is_superuser:
        user_devices = Device.objects.all()
    else:
        user_devices = request.user.allowed_devices.all()

    if selected_device_mac:
        device = user_devices.filter(pk=selected_device_mac).first()
    else:
        # Αλλιώς, πάρε την πρώτη από προεπιλογή (όπως έκανε πριν)
        device = user_devices.first()

    timestamps, soc_data, soh_data, voltage_data, current_data, temp_data, power_data = [], [], [], [], [], [], []
    
    if device:
        # Φέρνουμε τις τελευταίες 20 μετρήσεις και τις βάζουμε σε χρονολογική σειρά
        measurements = Measurement.objects.filter(device=device).order_by('-timestamp')[:200]
        
        for m in reversed(measurements):
            timestamps.append(m.timestamp.strftime('%H:%M:%S'))
            soc_data.append(m.soc if m.soc is not None else 0)
            soh_data.append(m.soh if m.soh is not None else 100)
            voltage_data.append(m.voltage)
            current_data.append(m.current)
            temp_data.append(m.temperature)
            power_data.append(m.power if m.power is not None else 0)

    context = {
        'devices': user_devices,
        'selected_device': device,
        'timestamps': json.dumps(timestamps),
        'soc_data': json.dumps(soc_data),
        'soh_data': json.dumps(soh_data),
        'voltage_data': json.dumps(voltage_data),
        'current_data': json.dumps(current_data),
        'power_data': json.dumps(power_data),
        'temp_data': json.dumps(temp_data),
    }
    
    return render(request, 'home.html', context)

# ========================================================================
# 2. FLEET DASHBOARD 
# ========================================================================
@login_required
def fleet_dashboard(request):
    # ΜΟΝΟ οι administrators έχουν πρόσβαση εδώ
    if not request.user.is_superuser:
        return redirect('/')

    all_devices = Device.objects.all()
    total_devices = all_devices.count()
    
    online_count = 0
    offline_count = 0
    alerts = []
    device_status_list = []
    
    # Θεωρούμε "Offline" μια συσκευή αν έχει να στείλει δεδομένα πάνω από 1 ώρα
    time_threshold = timezone.now() - timedelta(hours=1)

    for device in all_devices:
        latest = Measurement.objects.filter(device=device).order_by('-timestamp').first()
        is_online = False
        
        if latest:
            # Έλεγχος αν είναι Online
            if latest.timestamp >= time_threshold:
                is_online = True
                online_count += 1
            else:
                offline_count += 1
                
            # --- ΛΟΓΙΚΗ ΣΥΝΑΓΕΡΜΩΝ (ALERTS) ---
            if latest.temperature > 45.0:
                alerts.append({'device': device, 'type': 'danger', 'msg': f'Υπερθέρμανση: {latest.temperature}°C'})
            if latest.voltage < 10.5:
                alerts.append({'device': device, 'type': 'warning', 'msg': f'Κρίσιμη Τάση: {latest.voltage}V (Κίνδυνος φθοράς)'})
            if latest.soc is not None and latest.soc < 15.0:
                alerts.append({'device': device, 'type': 'warning', 'msg': f'Χαμηλή Μπαταρία: {latest.soc}%'})
        else:
            offline_count += 1 # Συσκευές χωρίς καμία μέτρηση είναι offline

        # Πακετάρουμε τα στοιχεία για τον πίνακα του HTML
        device_status_list.append({
            'device': device,
            'is_online': is_online,
            'latest': latest
        })

    context = {
        'total_devices': total_devices,
        'online_count': online_count,
        'offline_count': offline_count,
        'alerts': alerts,
        'device_status_list': device_status_list,
    }
    return render(request, 'fleet_dashboard.html', context)

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email") 

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email') 

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save() 
            login(request, user) 
            return redirect('/') 
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'registration/register.html', {'form': form})

# ------------------------------------------------------------------------
# ΑΛΛΑΓΗ 2: Η "Πόρτα" (API Endpoint) για να στέλνει δεδομένα ο ESP32
# ------------------------------------------------------------------------
BATTERY_CAPACITY_AH = 100.0  
@csrf_exempt  
def receive_sensor_data(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            mac = data.get('mac_address')
            
            try:
                device = Device.objects.get(mac_address=mac)
            except Device.DoesNotExist:
                return JsonResponse({'error': 'Unknown device. MAC address not found.'}, status=404)
            # Μετατροπή των τιμών σε δεκαδικούς (float)
            current_voltage = float(data.get('voltage'))
            current_amps = float(data.get('current'))
            current_temp = float(data.get('temperature'))
            #HARDWARE (Zero Clamping)
            if abs(current_amps) < 0.015:
                current_amps = 0.0
            if current_voltage < 1.0:
                current_voltage = 0.0
            power_watts = current_voltage * current_amps    
            now = timezone.now()
            
            # --- ΥΠΟΛΟΓΙΣΜΟΣ SoC & SoH (Coulomb Counting) ---
            last_measurement = Measurement.objects.filter(device=device).order_by('-timestamp').first()            
            if current_voltage >= 12.7:
                new_soc = 100.0 
            elif current_voltage <= 11.5:
                new_soc = 0.0
            else:
                new_soc = ((current_voltage - 11.5) / 1.2) * 100.0
                
            new_soh = 100.0
             
            
            if last_measurement and last_measurement.soc is not None:
                time_diff_seconds = (now - last_measurement.timestamp).total_seconds()
                time_diff_hours = time_diff_seconds / 3600.0
                battery_capacity = getattr(device, 'capacity_ah', 100.0)
                delta_soc = ((current_amps * time_diff_hours) / battery_capacity) * 100
                
                new_soc = last_measurement.soc + delta_soc
                new_soc = max(0.0, min(100.0, new_soc)) 
                new_soh = last_measurement.soh if last_measurement.soh else 100.0
            
            Measurement.objects.create(
                timestamp=now,
                device=device,
                voltage=current_voltage,
                current=current_amps,
                power=round(power_watts, 2),
                temperature=current_temp,
                soc=round(new_soc, 3), 
                soh=round(new_soh, 2)  
            )
            
            alert_message = None
            alert_subject = None

            #(Κόκκινος / Κίτρινος Συναγερμός)
            if current_temp > 45.0:
                alert_subject = f"DANGER: Battery Overheating ({device.name})"
                alert_message = f"Temperature has reached {current_temp}°C! Please check the system immediately."
            elif current_voltage < 11.0:
                alert_subject = f"DANGER: Deep Discharge ({device.name})"
                alert_message = f"Voltage has dropped to {current_voltage}V. Risk of irreversible damage."
            elif new_soc < 20.0:
                alert_subject = f"WARNING: Low Battery ({device.name})"
                alert_message = f"Battery level has dropped to {new_soc}%. The light should remain off."
            if alert_message:
                cache_key = f"alert_cooldown_{device.mac_address}"
                
                if not cache.get(cache_key):
                    try:
                        send_mail(
                            alert_subject,
                            alert_message,
                            os.getenv('EMAIL_HOST_USER_1'),
                            [os.getenv('EMAIL_USER_2')],
                            fail_silently=False,
                        )
                        print(f"Email sent: {alert_subject}")
                        cache.set(cache_key, True, 7200)
                    except Exception as e:
                        print(f"Error sending email: {e}")

            return JsonResponse({'status': 'Success! Data has been saved.'}, status=201)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
            
    return JsonResponse({'error': 'Only POST requests are allowed.'}, status=405)