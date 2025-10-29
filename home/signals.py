from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth.signals import user_logged_in
from .models import Nosozliklar, TexnikKorikJadval, Notification, EhtiyotQismlari

# === 1️⃣ Nosozlik bo‘yicha xabar ===
@receiver(post_save, sender=Nosozliklar)
def create_nosozlik_notification(sender, instance, created, **kwargs):
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

    if count < 2:
        return

    message = (
        f"{tarkib} tarkibida '{nosozlik_turi}' nosozligi {count}-chi marta qayd etildi."
    )

    Notification.objects.create(
        tarkib=tarkib,
        nosozlik_turi=nosozlik_turi,
        type="nosozlik",
        title="Takroriy nosozlik",
        message=message,
        count=count,
        is_read=False,
        seen=False,
    )

# === 2️⃣ Texnik ko‘rik bo‘yicha xabar ===
@receiver(user_logged_in)
def notify_today_checks(sender, user, request, **kwargs):
    from .models import TexnikKorikJadval
    today = timezone.now().date()
    today_checks = TexnikKorikJadval.objects.filter(sana=today)

    for korik in today_checks:
        depo = getattr(korik.tarkib, "depo", None)
        if not depo:
            continue

        texniklar = depo.users.filter(role="texnik")
        tamir_nomi = korik.tamir_turi.tamir_nomi if korik.tamir_turi else "noaniq tamir turi"

        for texnik in texniklar:
            Notification.objects.create(
                user=texnik,
                type="texnik_korik",
                title="Bugungi texnik ko‘rik",
                message=f"Bugun {korik.tarkib.tarkib_raqami} tarkib uchun '{tamir_nomi}' texnik ko‘rik rejalashtirilgan.",
                is_read=False,
                seen=False,
            )

# === 3️⃣ Ehtiyot qism kamayganda ===
@receiver(post_save, sender=EhtiyotQismlari)
def notify_low_stock(sender, instance, created, **kwargs):
    qoldiq = float(instance.jami_miqdor or 0)

    # Faqat 100 dan kam bo‘lsa yoki yangi yaratilganda
    if qoldiq < 100:
        title = "Ehtiyot qism kamaygani haqida" if not created else "Yangi ehtiyot qism kam miqdorda kiritildi"
        Notification.objects.create(
            ehtiyot_qism=instance,
            type="ehtiyot_qism",
            title=title,
            message=f"Omborda '{instance.ehtiyotqism_nomi}' nomli ehtiyot qism {int(qoldiq)} {instance.birligi} qoldi (100 tadan kam).",
            is_read=False,
            seen=False,
        )