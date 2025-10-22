from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import Nosozliklar, NosozlikNotification,TexnikKorikJadval, Notification
from django.contrib.auth.signals import user_logged_in

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
        
        
@receiver(user_logged_in)
def notify_today_checks(sender, user, request, **kwargs):
    """Foydalanuvchi tizimga kirganda bugungi texnik ko‘riklar uchun xabar yaratish"""
    today = timezone.now().date()

    # Bugungi sanada bo‘ladigan koriklar
    today_checks = TexnikKorikJadval.objects.filter(sana=today)

    for korik in today_checks:
        depo = getattr(korik.tarkib, "depo", None)
        if not depo:
            continue

        # Shu depo texnik foydalanuvchilariga xabar
        texniklar = depo.users.filter(role="texnik")  

        for texnik in texniklar:
            # Shu tarkib uchun bugungi xabar allaqachon bormi?
            exists = Notification.objects.filter(
                user=texnik,
                title="Bugungi texnik ko‘rik",
                message__icontains=str(korik.tarkib.tarkib_raqami),
                created_at__date=today
            ).exists()

            if not exists:
                Notification.objects.create(
                    user=texnik,
                    title="Bugungi texnik ko‘rik",
                    message=(
                        f"Bugun {korik.tarkib.tarkib_raqami} tarkib uchun "
                        f"'{korik.tamir_turi.tamir_nomi}' texnik ko‘rik rejalashtirilgan."
                    ),
                )