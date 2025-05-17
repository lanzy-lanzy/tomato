from django.db import models
from django.utils import timezone

class ESPDevice(models.Model):
    name = models.CharField(max_length=100, default="Tomato Sorter")
    ip_address = models.CharField(max_length=15, blank=True, null=True)
    last_seen = models.DateTimeField(auto_now=True)
    is_online = models.BooleanField(default=False)

    # Webcam configuration
    use_webcam = models.BooleanField(default=True)
    webcam_enabled = models.BooleanField(default=False)
    ripe_threshold_min = models.IntegerField(default=0)
    ripe_threshold_max = models.IntegerField(default=30)
    green_threshold_min = models.IntegerField(default=31)
    green_threshold_max = models.IntegerField(default=70)
    detection_sensitivity = models.IntegerField(default=70)

    DETECTION_MODES = (
        ('auto', 'Automatic'),
        ('manual', 'Manual'),
        ('hybrid', 'Hybrid'),
    )
    detection_mode = models.CharField(max_length=10, choices=DETECTION_MODES, default='manual')

    def __str__(self):
        return f"{self.name} ({self.ip_address})"

    @classmethod
    def get_default_device(cls):
        device, created = cls.objects.get_or_create(id=1)
        return device

class SortingSession(models.Model):
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    device = models.ForeignKey(ESPDevice, on_delete=models.CASCADE, related_name='sessions')

    def __str__(self):
        return f"Session {self.id} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"

    def end_session(self):
        self.end_time = timezone.now()
        self.is_active = False
        self.save()

    @property
    def duration(self):
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (timezone.now() - self.start_time).total_seconds()

    @property
    def total_tomatoes(self):
        return self.tomatoes.count()

    @property
    def ripe_count(self):
        return self.tomatoes.filter(is_ripe=True).count()

    @property
    def green_count(self):
        return self.tomatoes.filter(is_ripe=False).count()

class Tomato(models.Model):
    session = models.ForeignKey(SortingSession, on_delete=models.CASCADE, related_name='tomatoes')
    timestamp = models.DateTimeField(auto_now_add=True)
    is_ripe = models.BooleanField()

    def __str__(self):
        return f"{'Ripe' if self.is_ripe else 'Green'} Tomato - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
