# Nazim Hikmet Dijital Ikizi

Bu depo, Nazim Hikmet'in eserleri ve hakkinda yayinlanan icerikleri derlemek icin hazirlanmis bir ETL (Extract-Transform-Load) hattini barindirir. Kaynaklar manuel olarak tanimlanir ve otomatik kesif yapilmaz; yeni bir site eklemek icin `configs/sources.yaml` dosyasini duzenlemek yeterlidir.

> **Telif Uyarisi:** Nazim Hikmet eserlerinin tam metinleri 2033 yilina kadar telif haklarina tabidir. Bu depo telifli icerik barindirmasin diye SAFE_MODE secenegini ve filtre adimlarini kullanir; yine de depoyu herkese acmadan once yerel mevzuata uygunluk kontrolu yapmayi unutmayin.

## Ozellikler
- Moduler crawler mimarisi: siir sayfalari, Wikipedia listeleri, haber siteleri ve PDF kaynaklari icin ayri siniflar
- Esnek kaynak yapilandirmasi: oran sinirlari, pagination, CSS secicileri ve SAFE_MODE ile ozetleme
- Normalize -> Dedup -> Store -> Embed adimlarindan olusan ZenML hattinda MongoDB'ye kayit ve Qdrant'a vektor yukleme
- Docker Compose ile MongoDB, Qdrant ve crawler servisini birlikte calistirma
- FastAPI tabanli basit bir saglik ucu ve CLI ile elle tetikleme
- Qdrant + SentenceTransformers ile embedding destekli arama betikleri

## Kurulum ve Calistirma
1. Python 3.11+ ve Docker kurulu oldugundan emin olun. Yerel calisma icin sanal ortam olusturun:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```
   Docker tercih ediyorsaniz bu adimi atlayabilirsiniz.

2. Ortam degiskenlerini ayarlayin:
   ```bash
   cp .env.example .env
   ```
   En azindan `MONGO_URL`, `SAFE_MODE`, `EMBED_MODEL`, `QDRANT_HOST`, `QDRANT_PORT` ve `QDRANT_URL` degiskenlerini ihtiyaciniza gore guncelleyin. Docker Compose crawler servisi icinde Qdrant baglantisi varsayilan olarak `qdrant:6333` olacak sekilde override edilir; yerel calisma yapacaksaniz bu degerleri gecici olarak `localhost` vb. adreslere cekebilirsiniz. Tekrar calistirmalarda koleksiyonu sifirlamak isterseniz `QDRANT_RESET=true` secenegini kullanabilirsiniz.

3. Servisleri calistirin:
   ```bash
   docker compose up -d --build
   ```

4. Crawler'i tetikleyin:
   ```bash
   python -m src.ui.cli crawl
   # veya Docker konteyneri icinde ZenML pipeline'ini calistirin
   docker compose exec crawler zenml pipeline run crawl_pipeline
   # Belirli kaynaklar icin
   docker compose exec crawler zenml pipeline run crawl_pipeline -- --source_names "Kaynak 1" --source_names "Kaynak 2"
   ```
   Tek komutla calistirip servisleri durdurmak isterseniz `make crawl` ayni adimlari uygular.

5. Kayitlari dogrulayin:
   ```bash
   docker compose exec mongo mongosh --eval "use digital_twin; db.documents.countDocuments()"
   ```

## Kaynak Yapilandirmasi
Tum kaynaklar `configs/sources.yaml` dosyasinda saklanir. Ornek bir blok:

```yaml
SAFE_MODE: false
sources:
  - name: poems_from_index
    kind: poem_page
    base: "https://ornek-siir.org"
    seeds:
      - "https://ornek-siir.org/nazim-hikmet-siirleri"
    paging:
      next_css: "a.next"
      max_pages: 3
    extract:
      index_card_css: "ul.poem-list > li"
      detail_link_css: "a[href]"
      title_css: "h1.poem-title"
      full_css: "div.poem-text, pre"
```

- `kind` alanina gore ilgili crawler sinifi secilir (`poem_page`, `poem`, `news`, `pdf_poems` vb.).
- `SAFE_MODE` ortam degiskeni tanimliysa dosya ayarlarini ezer ve metinleri 250 karakterlik ozetlere indirger.
- PDF kaynaklari icin `collection`, `document_type`, `work_type` gibi ek alanlar bulunur.

## ETL Adimlari
1. **normalize:** Temel alanlari (title, author, text_full, year vb.) temizler ve standart hale getirir.
2. **dedup:** `hash` alanini kullanarak yinelenen kayitlari eler.
3. **store:** MongoDB'ye yazim yapar ve eksik indeksleri olusturur.
4. **embed:** Metinleri parcalara ayirip SentenceTransformers modeli ile vektore donusturur, Qdrant koleksiyonuna upsert eder.


## Komutlar
- `make up` -> `docker compose up -d --build`
- `make crawl` -> Docker icerisinde crawler pipeline'ini calistirir ve servisleri durdurur
- `make down` -> `docker compose down --remove-orphans`
- `make qdrant-up` -> Sadece Qdrant servisini baslatir
- `make embed` -> `src/etl/ingest_embeddings.py` ile Qdrant icin embedding yukler
- `make verify` -> `src/etl/verify_embeddings.py` betigiyle sorgu testi calistirir

### Değerlendirme (Eval)
Basit bir toplu değerlendirme için JSONL dosyaları ve bir komut satırı aracı eklendi:

```
python tools/eval_runner.py tests/eval/nazim_style_eval.jsonl
python tools/eval_runner.py tests/eval/nazim_bio_eval.jsonl
python tools/eval_runner.py tests/eval/nazim_rag_eval.jsonl
```

Çıktılar `outputs/eval/<set_adi>/<timestamp>/results.jsonl` altında toplanır. Cevaplar RAG bağlamı ve kaynak özetleriyle birlikte kaydedilir.

## Baseline v0 (nazim-twin-v0-baseline)
Bu referans sürüm, aşağıdaki temel ayarlarla dondurulmuştur:
- LLM (sağlayıcı/model): `ollama` + `llama3.2:3b-instruct` (varsayılan). `LLM_PROVIDER=openai_compat` ile OpenAI‑uyumlu sunucular kullanılabilir.
- Embedding: `intfloat/multilingual-e5-base` (sorgu: `query: ...`, pasaj: `passage: ...`, normalize edilmiş, cosine).
- Prompt (TR Persona): `build_nazim_prompt_tr` — Türkçe, Nazım odaklı, bağlama sıkı bağlı, [n] atıflı, güncel siyasal iknadan kaçınan yönergeler.
- Chunking:
  - Şiir: kıta (stanza) duyarlı, ~600 karakter üst sınırla paketleme.
  - Düz yazı: ~1200 karakter pencere, 150 üst üste binme; mümkün oldukça cümle sonuna hizalama.

Bu sürüm, sonraki iyileştirmelerin “v0’a göre daha iyi mi?” değerlendirmesi için referanstır.

ZenML tabanli pipeline'i calistirmak icin:
```bash
docker compose up -d --build
docker compose exec crawler zenml pipeline run crawl_pipeline
```
Pipeline tamamlandiginda dokumanlar MongoDB'ye kaydedilir ve ayni anda Qdrant koleksiyonuna vektorel olarak yuklenir.
Istege bagli olarak ZenML stack'i kaydetmek icin:
```bash
docker compose exec crawler bash -lc "zenml init . && zenml stack register local_stack -o default -a default -d default --set"
```

## Testler
Yerel ortamda pytest calistirabilirsiniz:
```bash
pytest
```

## Dizin Yapisi
```
.
|- configs/
|  |- sources.yaml
|- docker/
|  |- Dockerfile.crawler
|- src/
|  |- api/
|  |- crawler/
|  |- etl/
|  |- ui/
|  |- zen/
|- tests/
|  |- test_basic.py
|- docker-compose.yml
|- requirements.txt
|- Makefile
|- .env.example
```

## Gelistirme Ipuclari
- Buyuk veri dosyalari (`digital_twin.documents.json` gibi) repo disinda saklayin; `.gitignore` bu dosyalari dislar.
- `configs/sources.yaml` uzerindeki degisiklikleri versiyon kontrolunde tutarak veri toplama kaynaklarinin nasil evrildigini izleyin.
- MongoDB ve Qdrant container'larini uzun sure acik tutacaksaniz disk kullanimini izleyin; hacimler `mongo_data` ve `qdrant_storage` olarak tanimlanir.

## Lisans ve Telif
Kod MIT lisansi ile paylasilabilir (lisans dosyasi ekleyecekseniz uygun sekilde guncelleyiniz), ancak cekilen iceriklerin telif haklari orijinal sahiplerine aittir. Ticari veya kamuya acik kullanima gecmeden once hukuki kisitlari kontrol edin.

## Fine-Tuning (CPT/LoRA)
> Uyari: Tam metinlerin telif durumu 2033'e kadar surmektedir. Kendi ortaminizda, mevzuata uygun kullanim icin sorumluluk size aittir. Kurumsal/paylasimli ortamlarda yalnizca ozetlenmis veya kaynaklardan izinli icerik kullanin.

Bu depo, stil adaptasyonu icin basit bir “continued pretraining (CPT)” iskeleti sunar. Adimlar:

1. Korpus hazirla (dokumanlardan temiz metin cikar):
   ```bash
   python -m src.fine_tune.prepare_corpus \
     -- if needed set env: INPUT_JSON=digital_twin.documents.json CORPUS_DIR=data/corpus
   ```
   Bu adim `data/corpus/train.txt` ve `data/corpus/val.txt` uretir.

2. Egitim bagimliliklarini kur:
   ```bash
   pip install -r requirements-train.txt
   ```

3. Egitimi baslat (varsayilan ayarlar icin):
   ```bash
   # .env veya configs/finetune.yaml icindeki degiskenlerle override edebilirsiniz
   BASE_MODEL=meta-llama/Llama-3.2-3B-Instruct \
   OUTPUT_DIR=outputs/nazim-cpt \
   CORPUS_DIR=data/corpus \
   python -m src.fine_tune.train_cpt
   ```

Egitim tamamlaninca `outputs/nazim-cpt` altinda kontrol noktalarini ve `metrics.json` dosyasini bulursunuz. Bu iskelet tam metin uzerine devam egitimi (CPT) uygular; LoRA/QLoRA ve daha ileri metrikler icin TRL/PEFT ile genisletilebilir.

RAG + Fine-tune entegrasyonu: Egitimden sonra yerel LLM provider'i (Ollama veya OpenAI uyumlu sunucu) yerine, egitilen modeli servis ederek `src/api/app.py` altindaki `/ask` ucundan baglayabilirsiniz.
