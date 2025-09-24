from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.conf import settings


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ("monitoring", "Monitoring"),
        ("texnik", "Texnik"),
        ("skladchi", "Skladchi"),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    depo = models.ForeignKey(
        "ElektroDepo",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="users"
    )

    def __str__(self):
        return f"{self.username} - {self.role} ({self.depo.qisqacha_nomi if self.depo else 'Depo yo‘q'})"



class TamirTuri(models.Model):
    tamir_nomi = models.CharField(max_length=255)

    # masofa uchun
    tamirlash_davri = models.CharField(
        max_length=50,
        help_text="Masofa bo‘yicha: 5505 ± 10 km"
    )

    # vaqt uchun
    Vaqt_Choices = [
        ("soat", "Soat"),
        ("kun", "Kun"),
        ("oy", "Oy"),
    ]
    tamirlanish_miqdori = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Vaqt soni: masalan, 4"
    )
    tamirlanish_vaqti = models.CharField(
        max_length=10,
        choices=Vaqt_Choices,
        help_text="Vaqt birligi: soat/kun/oy"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Masalan: "To-1 (5000 km, 4 soat)"
        return f"{self.tamir_nomi} ({self.tamirlash_davri}, {self.tamirlanish_miqdori} {self.tamirlanish_vaqti})"


class ElektroDepo(models.Model):
    depo_nomi = models.CharField(max_length=255)
    qisqacha_nomi = models.CharField(max_length=50)
    joylashuvi = models.CharField(max_length=255)
    image = models.ImageField(upload_to="depo/", blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.depo_nomi
    

class EhtiyotQismlari(models.Model):
    ehtiyotqism_nomi = models.CharField(max_length=255, unique=True)
    nomenklatura_raqami = models.CharField(max_length=100)
    birligi = models.CharField(
        max_length=50,
        choices=[
            ("dona", "Dona"),
            ("para", "Para"),
            ("metr", "Metr"),
            ("litr", "Litr"),
        ],
        default="dona"
    )
    depo = models.ForeignKey(
        "ElektroDepo",
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    miqdori = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ehtiyotqism_nomi} ({self.birligi})"


# ✅ ManyToMany uchun oraliq jadval
class TexnikKorikEhtiyotQism(models.Model):
    korik = models.ForeignKey('TexnikKorik',on_delete=models.SET_NULL, null=True, blank=True)
    ehtiyot_qism = models.ForeignKey('EhtiyotQismlari',on_delete=models.SET_NULL, null=True, blank=True)
    miqdor = models.PositiveIntegerField(default=1)

    
    def save(self, *args, **kwargs):
        if self.ehtiyot_qism:
            if self.pk:
                # 🔄 update holati
                old = TexnikKorikEhtiyotQism.objects.get(pk=self.pk)
                farq = self.miqdor - old.miqdor  # yangi va eski miqdor farqi
                if farq > 0:  # ko‘proq ishlatilsa
                    if self.ehtiyot_qism.miqdori < farq:
                        raise ValueError("❌ Yetarli ehtiyot qism yo‘q!")
                    self.ehtiyot_qism.miqdori -= farq
                elif farq < 0:  # kamroq ishlatilsa
                    self.ehtiyot_qism.miqdori += abs(farq)
            else:
                # 🆕 yangi yozuv
                if self.ehtiyot_qism.miqdori < self.miqdor:
                    raise ValueError("❌ Yetarli ehtiyot qism yo‘q!")
                self.ehtiyot_qism.miqdori -= self.miqdor

            self.ehtiyot_qism.save()

        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.korik} - {self.ehtiyot_qism} ({self.miqdor})"



class TexnikKorikEhtiyotQismStep(models.Model):
    korik_step = models.ForeignKey('TexnikKorikStep',on_delete=models.SET_NULL, null=True, blank=True)
    ehtiyot_qism = models.ForeignKey('EhtiyotQismlari',on_delete=models.SET_NULL, null=True, blank=True)
    miqdor = models.PositiveIntegerField(default=1)
    
    
    def save(self, *args, **kwargs):
        if self.ehtiyot_qism:
            if self.pk:
                old = TexnikKorikEhtiyotQismStep.objects.get(pk=self.pk)
                farq = self.miqdor - old.miqdor
                if farq > 0:
                    if self.ehtiyot_qism.miqdori < farq:
                        raise ValueError("❌ Yetarli ehtiyot qism yo‘q!")
                    self.ehtiyot_qism.miqdori -= farq
                elif farq < 0:
                    self.ehtiyot_qism.miqdori += abs(farq)
            else:
                if self.ehtiyot_qism.miqdori < self.miqdor:
                    raise ValueError("❌ Yetarli ehtiyot qism yo‘q!")
                self.ehtiyot_qism.miqdori -= self.miqdor

            self.ehtiyot_qism.save()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.korik_step} - {self.ehtiyot_qism} ({self.miqdor})"
        






    
    
    
class HarakatTarkibi(models.Model):
    depo = models.ForeignKey("ElektroDepo", related_name="tarkiblar",
                             on_delete=models.SET_NULL, null=True, blank=True)
    guruhi = models.CharField(max_length=100)
    turi = models.CharField(max_length=100)
    tarkib_raqami = models.CharField(max_length=255, blank=True, null=True)  
    ishga_tushgan_vaqti = models.DateField()
    eksplutatsiya_vaqti = models.BigIntegerField(help_text="km da")
    image = models.ImageField(upload_to="tarkiblar/", blank=True, null=True)

    holati = models.CharField(
        choices=[
            ("Soz_holatda", "Soz_holatda"),
            ("Texnik_korikda", "Texnik_korikda"),
            ("Nosozlikda", "Nosozlikda"),
        ],
        max_length=100,
        default="Soz_holatda"
    )

    # 🔹 versionlash maydonlari
    is_active = models.BooleanField(default=True)  
    previous_version = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="next_versions"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def update_tarkib_raqami(self):
        """Tarkib raqamini avtomatik yig‘ish."""
        vagonlar = self.vagonlar.order_by("id").values_list("vagon_raqami", flat=True)
        self.tarkib_raqami = "-".join(vagonlar)
        self.save(update_fields=["tarkib_raqami"])

    def __str__(self):
        return f"{self.tarkib_raqami or 'tarkib'} ({'active' if self.is_active else 'archived'})"



class Vagon(models.Model):
    tarkib = models.ForeignKey(
        "HarakatTarkibi", related_name="vagonlar",
        on_delete=models.CASCADE,
    )
    vagon_raqami = models.CharField(max_length=50)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # 🔹 Har safar vagon qo‘shilganda/yangilanganda tarkib raqami yangilanadi
        if self.tarkib:
            self.tarkib.update_tarkib_raqami()

    def delete(self, *args, **kwargs):
        tarkib = self.tarkib
        super().delete(*args, **kwargs)
        # 🔹 Vagon o‘chirilib ketganda ham tarkib raqami yangilansin
        if tarkib:
            tarkib.update_tarkib_raqami()

    def __str__(self):
        return f"{self.vagon_raqami} ({self.tarkib.tarkib_raqami})"

    
    
class KunlikYurish(models.Model):
    tarkib = models.ForeignKey(
        HarakatTarkibi,
        on_delete=models.SET_NULL,
        null=True,
        related_name="kunlik_yurishlar"
    )
    sana = models.DateField(default=timezone.now)
    kilometr = models.PositiveIntegerField(help_text="Yurilgan km")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sana", "-id"]

    def __str__(self):
        return f"{self.tarkib.tarkib_raqami} - {self.sana} - {self.kilometr} km"
 


class TexnikKorik(models.Model):
    class Status(models.TextChoices):
        JARAYONDA = "Texnik_korikda", "Texnik_korikda"
        BARTARAF_ETILDI = "Soz_holatda", "Soz_holatda"

    tarkib = models.ForeignKey('HarakatTarkibi',on_delete=models.SET_NULL,limit_choices_to={"is_active": True}, null=True, blank=True,related_name="koriklar")
    tamir_turi = models.ForeignKey('TamirTuri',on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.JARAYONDA, editable=False)
    ehtiyot_qismlar = models.ManyToManyField("EhtiyotQismlari", through="TexnikKorikEhtiyotQism", blank=True)
    kamchiliklar_haqida = models.TextField(blank=True)
    bartaraf_etilgan_kamchiliklar = models.TextField(blank=True)
    kirgan_vaqti = models.DateTimeField(default=timezone.now)
    chiqqan_vaqti = models.DateTimeField(null=True, blank=True)
    akt_file = models.FileField(upload_to="texnik_korik_aktlar/", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    yakunlash = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.id:
            ongoing = TexnikKorik.objects.filter(
                tarkib=self.tarkib,
                status=TexnikKorik.Status.JARAYONDA
            )
            if ongoing.exists():
                raise ValueError("Bu tarkib bo'yicha yakunlanmagan texnik ko'rik mavjud!")

            self.kirgan_vaqti = timezone.now()
            self.status = TexnikKorik.Status.JARAYONDA

            self.tarkib.holati = "Texnik_korikda"
            self.tarkib.save()

        else:
            old = TexnikKorik.objects.filter(id=self.id).first()
            if old:
                self.kirgan_vaqti = old.kirgan_vaqti

        # ❌ yakunlash tekshiruvini olib tashladik
        super().save(*args, **kwargs)


class TexnikKorikStep(models.Model):
    class Status(models.TextChoices):
        JARAYONDA = "Jarayonda", "Jarayonda"
        BARTARAF_ETILDI = "Yakunlandi", "Yakunlandi"
    korik = models.ForeignKey(TexnikKorik, on_delete=models.SET_NULL,null=True, blank=True, related_name="steps")
    tamir_turi = models.ForeignKey('TamirTuri', on_delete=models.SET_NULL, null=True, blank=True)
    ehtiyot_qismlar = models.ManyToManyField(
    "EhtiyotQismlari",
    through="TexnikKorikEhtiyotQismStep",
    blank=True
    )
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.JARAYONDA
    )
    kamchiliklar_haqida = models.TextField(blank=True)
    bartaraf_etilgan_kamchiliklar = models.TextField(blank=True)
    akt_file = models.FileField(upload_to="akt/", null=True, blank=True)
    chiqqan_vaqti = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Step qo'shish faqat yakunlanmagan korikka
        if self.korik.status == TexnikKorik.Status.BARTARAF_ETILDI:
            raise ValueError("Bu korik yakunlangan, yangi step qo'shib bo'lmaydi!")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Step: {self.korik.tarkib} — {self.created_by}"



class NosozlikEhtiyotQismStep(models.Model):
    step = models.ForeignKey('NosozlikStep', on_delete=models.SET_NULL,null=True, blank=True, related_name="ehtiyot_qismlar_step")
    ehtiyot_qism = models.ForeignKey('EhtiyotQismlari', on_delete=models.SET_NULL,null=True, blank=True,)
    miqdor = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.step} - {self.ehtiyot_qism.ehtiyotqism_nomi} ({self.miqdor} {self.ehtiyot_qism.birligi})"



class NosozlikEhtiyotQism(models.Model):
    nosozlik = models.ForeignKey("Nosozliklar", on_delete=models.SET_NULL,null=True, blank=True, related_name="ehtiyot_qism_aloqalari")
    ehtiyot_qism = models.ForeignKey("EhtiyotQismlari", on_delete=models.SET_NULL,null=True, blank=True,)
    miqdor = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.ehtiyot_qism.ehtiyotqism_nomi} - {self.miqdor} {self.ehtiyot_qism.birligi}"

    def save(self, *args, **kwargs):
        # Agar kerak bo'lsa, miqdorni float qilish yoki maxsus formatlash
        if self.ehtiyot_qism.birligi.lower() == "litr" and not isinstance(self.miqdor, float):
            self.miqdor = float(self.miqdor)
        super().save(*args, **kwargs)



class Nosozliklar(models.Model):
    class Status(models.TextChoices):
        JARAYONDA = "Nosozlikda", "Nosozlikda"
        BARTARAF_ETILDI = "Soz_holatda", "Soz_holatda"

    ehtiyot_qismlar = models.ManyToManyField(
        "EhtiyotQismlari",
        through="NosozlikEhtiyotQism",
        related_name="nosozliklar",
        blank=True
    )
    tarkib = models.ForeignKey('HarakatTarkibi', on_delete=models.SET_NULL,limit_choices_to={"is_active": True},null=True, blank=True, related_name="nosozliklar")
    nosozliklar_haqida = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.JARAYONDA, editable=False)

    aniqlangan_vaqti = models.DateTimeField(default=timezone.now)         
    bartarafqilingan_vaqti = models.DateTimeField(null=True, blank=True)

    bartaraf_etilgan_nosozliklar = models.TextField(blank=True, help_text="Bartaraf etilish jarayonida bajarilgan ishlar")
    image = models.ImageField(upload_to="nosozlik_images/", blank=True)
    akt_file = models.FileField(upload_to="nosozlik_aktlar/", null=True, blank=True) 

    created_by = models.ForeignKey("CustomUser", on_delete=models.SET_NULL, null=True, blank=True)
    yakunlash = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.id:
            self.aniqlangan_vaqti = timezone.now()
            self.status = Nosozliklar.Status.JARAYONDA
            self.tarkib.holati = "Nosozlikda"
            self.tarkib.save()
        else:
            old = Nosozliklar.objects.filter(id=self.id).first()
            if old:
                self.aniqlangan_vaqti = old.aniqlangan_vaqti

        # ❌ yakunlash tekshiruvini olib tashlaymiz
        super().save(*args, **kwargs)


        def __str__(self):
            return f"{self.tarkib} - {self.status} ({self.created_by})"

    @property
    def ehtiyot_qismlar_miqdor(self):
        result = []
        for eq in self.ehtiyot_qismlar.all():
            through_obj = NosozlikEhtiyotQism.objects.get(nosozlik=self, ehtiyot_qism=eq)
            result.append(f"{eq.ehtiyotqism_nomi} - {through_obj.miqdor} {eq.birligi}")
        return result




class NosozlikStep(models.Model):
    class Status(models.TextChoices):
        JARAYONDA = "Jarayonda", "Jarayonda"
        BARTARAF_ETILDI = "Yakunlandi", "Yakunlandi"

    nosozlik = models.ForeignKey(Nosozliklar, on_delete=models.SET_NULL,null=True, blank=True, related_name="steps")
    tamir_turi = models.ForeignKey('TamirTuri', on_delete=models.SET_NULL, null=True, blank=True)
    ehtiyot_qismlar = models.ManyToManyField(
        'EhtiyotQismlari',
        through='NosozlikEhtiyotQismStep',
        blank=True
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.JARAYONDA)
    nosozliklar_haqida = models.TextField(blank=True)
    bartaraf_etilgan_nosozliklar = models.TextField(blank=True)
    akt_file = models.FileField(upload_to='nosozlik_step_aktlar/', null=True, blank=True)
    bartaraf_qilingan_vaqti = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey('CustomUser', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Step faqat yakunlanmagan nosozliklarga qo‘shiladi
        if self.nosozlik.status == Nosozliklar.Status.BARTARAF_ETILDI:
            raise ValueError("Bu nosozlik yakunlangan, yangi step qo'shib bo'lmaydi!")

        # Agar step yakunlanayotgan bo‘lsa
        if self.bartaraf_qilingan_vaqti and self.akt_file:
            self.status = self.Status.BARTARAF_ETILDI

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nosozlik.tarkib} — Step ({self.status})"