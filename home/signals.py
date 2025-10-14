from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Nosozliklar, NosozlikNotification

@receiver(post_save, sender=Nosozliklar)
def create_notification_for_repeated_nosozlik(sender, instance, created, **kwargs):
    if not created:
        return

    tarkib = instance.tarkib
    if not tarkib or not instance.nosozliklar_haqida:
        return

    nosozlik_turi = instance.nosozliklar_haqida.nosozlik_turi

    count = Nosozliklar.objects.filter(
        tarkib=tarkib,
        nosozliklar_haqida__nosozlik_turi=nosozlik_turi
    ).count()

    if count >= 2:
        first_obj = Nosozliklar.objects.filter(
            tarkib=tarkib,
            nosozliklar_haqida__nosozlik_turi=nosozlik_turi
        ).earliest("created_at")

        message = (
            f"{tarkib} tarkibida '{nosozlik_turi}' nosozligi {count}-chi marta qayd etildi.\n"
            f"Birinchi holat: {first_obj.created_at.strftime('%d-%m-%Y')}, "
            f"So‘nggi holat: {timezone.now().strftime('%d-%m-%Y')}."
        )

        NosozlikNotification.objects.create(
            tarkib=tarkib,
            nosozlik_turi=nosozlik_turi,
            count=count,
            message=message,
            first_occurrence=first_obj.created_at,
            last_occurrence=timezone.now()
        )

        print(f"🔔 {message}")