from django.db import models
from django.contrib.auth.models import User

class Device(models.Model):
    # Κάνουμε το MAC Address Primary Key για να διασφαλίσουμε ότι κάθε συσκευή είναι μοναδική
    mac_address = models.CharField(max_length=17, primary_key=True, help_text="π.χ. AA:BB:CC:DD:EE:FF")
    name = models.CharField(max_length=100, help_text="Ένα όνομα, π.χ. 'Μπαταρία Ταράτσας'")
    
    # Το ManyToManyField δημιουργεί αυτόματα τον "Πίνακα 3" που λέγαμε, συνδέοντας πολλούς χρήστες με πολλές συσκευές.
    users = models.ManyToManyField(User, related_name='allowed_devices', blank=True)

    def __str__(self):
        return f"{self.name} ({self.mac_address})"

    
# Πίνακας 3: Μετρήσεις (Measurements)
class Measurement(models.Model):
    # Το timestamp ως Primary Key για να διασφαλίσουμε ότι κάθε μέτρηση είναι μοναδική και να έχουμε αυτόματα την χρονολογική σειρά.
    timestamp = models.DateTimeField(primary_key=True)
    
    # Συνδέουμε τη μέτρηση με τον συγκεκριμένο ESP32 
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='measurements')
    
    # Οι μετρήσεις των αισθητήρων 
    voltage = models.FloatField(verbose_name="Τάση (V)")
    current = models.FloatField(verbose_name="Ρεύμα (A)")
    temperature = models.FloatField(verbose_name="Θερμοκρασία (°C)")
    soc = models.FloatField(verbose_name="State of Charge (%)", null=True, blank=True)  
    soh = models.FloatField(verbose_name="State of Health (%)", null=True, blank=True)  
    power = models.FloatField(verbose_name="Ισχύς (W)", null=True, blank=True)

    class Meta:
        # Αυτό λέει στη βάση να φέρνει πάντα τα δεδομένα ταξινομημένα από το πιο πρόσφατο στο πιο παλιό
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.device.mac_address} - {self.timestamp}"
