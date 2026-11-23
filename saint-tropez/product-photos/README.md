# Fotos de productos · Saint Tropez Market 24/7

`checklist.csv` lista los 148 productos (ábrelo en Excel o Google Sheets):

- **120 productos de marca** → foto oficial del **distribuidor / proveedor**.
- **28 productos genéricos** (frutas, panadería, huevos, hielo, vinos sin marca…) → fotos de stock de Unsplash.

La columna **"nombre de archivo"** es el nombre exacto que debe tener cada foto (por ejemplo `d101-induveca-salami-super-especial.webp`). Si el nombre coincide, la web la muestra sola.

## 1. Qué pedir a cada distribuidor

Mensaje listo para enviar:

> Buenas, somos **Saint Tropez Market 24/7** (Downtown Punta Cana). Vamos a vender sus productos en nuestra tienda en línea y necesitamos las **fotos oficiales de producto (packshots)** de las presentaciones que compramos:
> - Foto frontal del empaque actual, **fondo blanco o transparente** (PNG o JPG).
> - Mínimo **800 × 800 px**, sin marcas de agua.
> - Una foto por presentación (adjuntamos la lista).
>
> También les agradecemos confirmar que podemos usarlas en nuestra web y redes para promocionar sus productos. ¡Gracias!

Adjunta las filas del `checklist.csv` de esa marca.

## 2. Subir las fotos

1. Renombra cada foto con su **nombre de archivo** del checklist (la extensión puede ser `.webp`, `.jpg` o `.png`).
2. Supabase → **Storage** → bucket **`st-products`** → **Upload files**. (Máximo 3 MB por foto.)
3. Supabase → **SQL Editor**, ejecuta una sola vez (enlaza todas las fotos subidas con su producto):

```sql
update public.st_products p
set img = 'https://nwzcezwlszozicifmile.supabase.co/storage/v1/object/public/st-products/' || o.name,
    updated_at = now()
from storage.objects o
where o.bucket_id = 'st-products' and o.name like p.id || '-%';
```

Vuelve a ejecutarla cada vez que subas fotos nuevas. La web las muestra al recargar.

**Cómo se ven:** las fotos de marca se muestran completas sobre el fondo claro de cada categoría; las fotos de comida llenan el recuadro.

## 3. Origen y derechos

- Usa solo fotos que el distribuidor o la marca te entreguen (o que tú tomes de tus productos). No copies fotos de otras webs.
- Algunas marcas internacionales se fabrican o envasan en RD: confirma el país de origen de cada presentación y corrígelo en `st_products.origin` si hace falta.
