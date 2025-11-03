from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth.signals import user_logged_in
from django.contrib.auth import get_user_model
from .models import Nosozliklar, Notification, EhtiyotQismlari, UserNotificationStatus, TexnikKorikJadval

User = get_user_model()


# === 1️⃣ Nosozlik bo‘yicha xabar ===
@receiver(post_save, sender=Nosozliklar)
def create_or_update_nosozlik_notification(sender, instance, created, **kwargs):
    if not created:  # faqat yangi yozilganda ishlasin
        return

    # print(f"🔔 SIGNAL ISHGA TUSHDI | ID={instance.id} | created={created}")

    tarkib = instance.tarkib
    nosozlik_haqida = instance.nosozliklar_haqida
    if not tarkib or not nosozlik_haqida:
        return

    nosozlik_turi = nosozlik_haqida.nosozlik_turi

    total_count = Nosozliklar.objects.filter(
        tarkib=tarkib,
        nosozliklar_haqida__nosozlik_turi=nosozlik_turi
    ).count()

    print(f"📊 total_count = {total_count}")

    if total_count < 2:
        return

    display_count = total_count - 1

    last_notif = (
        Notification.objects
        .filter(tarkib=tarkib, nosozlik_turi=nosozlik_turi, type="nosozlik")
        .order_by("-created_at")
        .first()
    )

    if last_notif:
        if last_notif.count != total_count:
            print("🔁 Mavjud xabar yangilanmoqda")
            last_notif.count = total_count
            last_notif.title = f"Nosozlik {display_count}-marta takrorlandi"
            last_notif.message = f"{tarkib} tarkibida '{nosozlik_turi}' nosozligi {display_count}-marta qayd etildi."
            last_notif.last_occurrence = timezone.now()
            last_notif.save(update_fields=["count", "title", "message", "last_occurrence"])
    else:
        print("🆕 Yangi xabar yaratilmoqda")
        notif = Notification.objects.create(
            tarkib=tarkib,
            nosozlik_turi=nosozlik_turi,
            type="nosozlik",
            title=f"Nosozlik {display_count}-marta takrorlandi",
            message=f"{tarkib} tarkibida '{nosozlik_turi}' nosozligi {display_count}-marta qayd etildi.",
            count=display_count,
        )
        for user in User.objects.all():
            UserNotificationStatus.objects.create(user=user, notification=notif)


# === 2️⃣ Texnik ko‘rik bo‘yicha xabar (faqat bugun uchun) ===
@receiver(user_logged_in)
def notify_today_checks(sender, user, request, **kwargs):
    """Bugungi texnik ko‘riklar haqida texniklarga xabar yuborish."""
    today = timezone.now().date()
    today_checks = TexnikKorikJadval.objects.filter(sana=today)

    for korik in today_checks:
        depo = getattr(korik.tarkib, "depo", None)
        if not depo:
            continue

        texniklar = depo.users.filter(role="texnik")
        tamir_nomi = korik.tamir_turi.tamir_nomi if korik.tamir_turi else "noaniq tamir turi"

        for texnik in texniklar:
            notif = Notification.objects.create(
                user=texnik,
                type="texnik_korik",
                title="Bugungi texnik ko‘rik",
                message=f"Bugun {korik.tarkib.tarkib_raqami} tarkib uchun '{tamir_nomi}' texnik ko‘rik rejalashtirilgan.",
            )
            UserNotificationStatus.objects.create(user=texnik, notification=notif)



# === 3️⃣ Ehtiyot qism kamayganda (update paytida) ===
@receiver(pre_save, sender=EhtiyotQismlari)
def store_old_stock(sender, instance, **kwargs):
    """Yangilanishdan oldingi miqdorni saqlaymiz."""
    if instance.pk:
        try:
            old_instance = EhtiyotQismlari.objects.get(pk=instance.pk)
            instance._old_jami_miqdor = float(old_instance.jami_miqdor or 0)
        except EhtiyotQismlari.DoesNotExist:
            instance._old_jami_miqdor = None
    else:
        instance._old_jami_miqdor = None


@receiver(post_save, sender=EhtiyotQismlari)
def notify_low_stock(sender, instance, created, **kwargs):
    """Ehtiyot qism 100 tadan kamayganda faqat update paytida xabar beradi."""
    if created:
        return  # yangi yaratilganda chiqmasin

    old_qoldiq = getattr(instance, "_old_jami_miqdor", None)
    new_qoldiq = float(instance.jami_miqdor or 0)

    # Agar eski 100 dan katta bo‘lib, yangi 100 dan kichik bo‘lsa — xabar chiqadi
    if old_qoldiq is not None and old_qoldiq >= 100 and new_qoldiq < 100:
        notif = Notification.objects.create(
            ehtiyot_qism=instance,
            type="ehtiyot_qism",
            title="Ehtiyot qism kamaygani haqida",
            message=f"Omborda '{instance.ehtiyotqism_nomi}' nomli ehtiyot qism "
                    f"{int(new_qoldiq)} {instance.birligi} qoldi (100 tadan kam).",
        )

        for user in User.objects.all():
            UserNotificationStatus.objects.create(user=user, notification=notif)



# === 4️⃣ Foydalanuvchi login qilganda 100 tadan kam bo‘lgan qismlar uchun xabar ===

@receiver(user_logged_in)
def notify_low_stock_on_login(sender, user, request, **kwargs):
    """Foydalanuvchi login qilganda 100 tadan kam bo‘lgan qismlar uchun xabar chiqadi."""
    
    # Kirimlar jamini olish
    items = EhtiyotQismlari.objects.all()
    
    for item in items:
        # jami_miqdor ni property orqali hisoblaymiz
        qoldiq = item.jami_miqdor

        if qoldiq < 100:
            # Shu user uchun shu qismlik xabar avval yaratilgan bo‘lmasa
            existing = UserNotificationStatus.objects.filter(
                user=user,
                notification__ehtiyot_qism=item,
                notification__type="ehtiyot_qism"
            ).exists()

            if not existing:
                notif = Notification.objects.create(
                    ehtiyot_qism=item,
                    type="ehtiyot_qism",
                    title="Ehtiyot qism kamaygani haqida",
                    message=(
                        f"Omborda '{item.ehtiyotqism_nomi}' nomli ehtiyot qism "
                        f"{int(qoldiq)} {item.birligi} qoldi (100 tadan kam)."
                    ),
                )
                UserNotificationStatus.objects.create(user=user, notification=notif)
