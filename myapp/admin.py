from django.contrib import admin
from .models import Device, Measurement

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'mac_address')  
    search_fields = ('name', 'mac_address') 
    filter_horizontal = ('users',)          

# Κάνουμε register τις Μετρήσεις (Measurement)
@admin.register(Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'device', 'voltage', 'current', 'temperature', 'soc', 'soh')  # Τι θα φαίνεται στη λίστα
    search_fields = ('device__name', 'device__mac_address') # Μπάρα αναζήτησης με βάση το όνομα ή το MAC της συσκευής
    list_filter = ('device',)               # Φίλτρο στα δεξιά
    date_hierarchy = 'timestamp'            # Μενού πλοήγησης ανά ημερομηνία
