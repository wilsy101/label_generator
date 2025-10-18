import csv
import io
import os
import zipfile
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings
from django.core.files.base import ContentFile
from .models import ProductLabel
import barcode
from barcode.writer import ImageWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

def process_csv(csv_upload):
    print("Process CSV called")
    """Process CSV file and create ProductLabel instances (using uploaded barcode images)."""
    file_path = csv_upload.file.path

    # Fixed manufacturer text
    manufacturer_text = """Trisa Exports Pvt. Ltd. 
    E-2, Shree Arihant Compound, Ground Floor,
    Gala No. 1 to 8, Kalher, Bhiwandi,
    Thane - 421302, Maharashtra, India.
    For any concerns or issues, please
    Email us at support@trisa.co.in
    Call us at: +91 9156224974"""

    try:
        # --- Detect encoding ---
        try:
            encoder = 'cp1252'
            with open(file_path, mode='r', encoding=encoder) as f:
                reader = csv.DictReader(f)
                print(f"Testing encoder with {encoder} for Product: {next(reader).get('ProductName')}")
                csv_upload.labels.all().delete()
        except Exception:
            encoder = 'utf-8'
            with open(file_path, mode='r', encoding=encoder) as f:
                reader = csv.DictReader(f)
                print(f"Testing encoder with {encoder} for Product: {next(reader).get('ProductName')}")

        # --- Build barcode lookup from uploaded files ---
        barcode_map = {}
        if hasattr(csv_upload, "barcodes"):
            for barcode_obj in csv_upload.barcodes.all():
                filename = os.path.basename(barcode_obj.image.name).lower()
                if filename.startswith("ean_") and filename.endswith(".png"):
                    gtin = filename[4:-4]  # extract GTIN from filename (EAN_<GTIN>.png)
                    barcode_map[gtin] = barcode_obj.image.path

        # --- Read CSV and create labels ---
        with open(file_path, mode='r', encoding=encoder) as f:
            print("Opened CSV for processing...")
            reader = csv.DictReader(f)

            for row in reader:
                product_name = row.get('ProductName', '')
                print(f"Processing product: {product_name}")

                gtin = str(row.get('GTINs') or row.get('GTIN') or '').strip()
                barcode_path = barcode_map.get(gtin.lower()) if gtin else None

                label = ProductLabel.objects.create(
                    csv_upload=csv_upload,
                    product_name=product_name,
                    mrp=row.get('MRP', ''),
                    quality=row.get('Quality', ''),
                    size=row.get('Size', ''),
                    net_quantity=row.get('Net Quantity', ''),
                    product_code=row.get('Product Code', ''),
                    design_color=row.get('Design / Color', ''),
                    mfg_month='',
                    mfg_year='',
                    gtin=gtin,
                    manufacturer=manufacturer_text
                )

                # Parse Mth & Year of Mfg. column
                mfg_date = row.get('Mth & Year of Mfg.', '')
                if mfg_date:
                    parts = mfg_date.split()
                    label.mfg_month = parts[0] if len(parts) > 0 else ''
                    label.mfg_year = parts[1] if len(parts) > 1 else ''
                    label.save()

                # --- Generate label image (with or without barcode) ---
                image_file = generate_label_image(label, barcode_path=barcode_path)
                label.image.save(f'label_{label.id}.png', image_file, save=True)

    except Exception as e:
        print(f"Couldn't complete label creation. Error: {e}")

    csv_upload.processed = True
    csv_upload.save()

def generate_label_image(label, barcode_path=None):
    """Generate label image with specifications, improved margins, and bold labels."""
    # Image dimensions: 2 inches x 3 inches at 300 DPI
    dpi = 300
    width = int(2 * dpi)  # 600 pixels
    height = int(3 * dpi)  # 900 pixels

    # Create RGB image
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)

    # Define the font color
    FONT_COLOR = '#8B634B'  # (Pantone 876 C to hex conversion)

    # Border and padding
    border_width = 2
    border_padding_offset = 15
    padding = 20

    # Draw border
    draw.rectangle(
        [(border_padding_offset, border_padding_offset),
         (width - border_padding_offset, height - border_padding_offset)],
        outline=FONT_COLOR,
        width=border_width
    )

    # --- Font setup ---
    target_point_size = 6.5
    visual_reduction_factor = 0.9
    calculated_pixel_size = target_point_size * dpi / 72
    font_size = int(calculated_pixel_size * visual_reduction_factor)
    if font_size < 10:
        font_size = 10

    bold_font_path = None
    try:
        font_dir = os.path.join(settings.BASE_DIR, 'static', 'style', 'fonts', 'myriad-pro')
        regular_font_path = os.path.join(font_dir, 'MYRIADPRO-REGULAR.OTF')
        bold_font_path = os.path.join(font_dir, 'MYRIADPRO-BOLD.OTF')
        font_normal = ImageFont.truetype(regular_font_path, font_size)
        font_bold = ImageFont.truetype(bold_font_path, font_size)
    except Exception as e:
        print(f"Font load failed: {e}")
        font_normal = ImageFont.load_default()
        font_bold = ImageFont.load_default()

    # Content layout
    x = border_padding_offset + border_width + padding
    y = border_padding_offset + border_width + padding
    line_height = int(font_size * 1.3)
    row_padding = line_height // 3

    # Table data
    table_data = [
        ('Product :', label.product_name),
        ('MRP :', label.mrp),
        ('Quality :', label.quality),
        ('Size :', label.size),
        ('Net Quantity :', label.net_quantity),
        ('Product Code :', label.product_code),
        ('Design / Color :', label.design_color),
        ('Mth & Year of Mfg. :', f"{label.mfg_month} {label.mfg_year}".strip())
    ]

    table_width = width - 2 * x
    label_column_width = int(table_width * 0.4)
    value_column_x = x + label_column_width + 8

    # Draw table
    for field_label, field_value in table_data:
        draw.text((x, y), field_label, font=font_bold, fill=FONT_COLOR)
        max_value_width = table_width - label_column_width - 8
        value_lines = wrap_text(field_value, font_normal, max_value_width)
        for i, value_line in enumerate(value_lines):
            draw.text((value_column_x, y + (i * line_height)),
                      value_line, font=font_normal, fill=FONT_COLOR)
        y += line_height * max(1, len(value_lines))
        y += row_padding

    y += int(line_height * 1.1)

    # Manufacturer info
    draw.text((x, y), 'Manufactured and Marketed By :', font=font_bold, fill=FONT_COLOR)
    y += line_height
    manufacturer_parts = label.manufacturer.split('\n')
    for part in manufacturer_parts:
        wrapped_lines = wrap_text(part, font_normal, width - 2 * x)
        for line in wrapped_lines:
            draw.text((x, y), line, font=font_normal, fill=FONT_COLOR)
            y += line_height

    y += line_height // 2
    y_barcode_block_start = y

    # --- Bottom "Make in India" text ---
    mii_text = "Make in India"
    mii_font_size = int(font_size * 1.2)
    font_make_in_india = font_bold
    try:
        if bold_font_path and os.path.exists(bold_font_path):
            font_make_in_india = ImageFont.truetype(bold_font_path, mii_font_size)
    except Exception:
        pass

    mii_width = draw.textlength(mii_text, font=font_make_in_india)
    mii_text_height = mii_font_size + (line_height // 4)
    x_mii_centered = (width - mii_width) / 2
    bottom_content_y = height - (border_padding_offset + border_width + padding)
    y_mii_start = bottom_content_y - mii_text_height
    barcode_available_height = y_mii_start - y_barcode_block_start
    barcode_target_height = int(barcode_available_height * 1.0)

    # --- Paste barcode image if available ---
    if barcode_path and os.path.exists(barcode_path):
        try:
            barcode_img = Image.open(barcode_path)
            if barcode_img.mode != 'RGB':
                barcode_img = barcode_img.convert('RGB')

            barcode_max_width = width - 2 * x
            ratio = barcode_img.width / barcode_img.height
            final_width = barcode_max_width
            final_height = int(final_width / ratio)

            if final_height > barcode_target_height:
                final_height = barcode_target_height
                final_width = int(final_height * ratio)

            if final_width > 0 and final_height > 0:
                barcode_img = barcode_img.resize((final_width, final_height), Image.Resampling.LANCZOS)
                x_centered = x + (barcode_max_width - final_width) // 2
                reserved_space_height = y_mii_start - y_barcode_block_start
                vertical_padding = (reserved_space_height - final_height) // 2
                y_barcode_paste = y_barcode_block_start + vertical_padding
                img.paste(barcode_img, (x_centered, y_barcode_paste))
        except Exception as e:
            print(f"Failed to paste barcode image: {e}")
    else:
        # Leave empty space for barcode (do nothing)
        pass

    # --- Draw "Make in India" text ---
    draw.text((x_mii_centered, y_mii_start), mii_text, font=font_make_in_india, fill=FONT_COLOR)

    # Save to bytes
    output = io.BytesIO()
    img.save(output, format='PNG', dpi=(dpi, dpi))
    output.seek(0)
    return ContentFile(output.read())

def wrap_text(text, font, max_width):
    """Wrap text to fit within max_width, respecting explicit newline characters."""
    if not text:
        return ['']
    
    final_lines = []
    
    # First, split the text by explicit newline characters
    segments = text.split('\n')
    
    # Use textlength to measure string width more accurately
    def get_text_width(text_to_measure, text_font):
        if hasattr(text_font, 'getlength'):
            return text_font.getlength(text_to_measure)
        # Fallback for default font where getlength might not be available or accurate
        return text_font.getsize(text_to_measure)[0] 

    for segment in segments:
        words = segment.split()
        current_line = []
        
        for word in words:
            if not current_line:
                current_line.append(word)
            else:
                test_line = ' '.join(current_line + [word])
                if get_text_width(test_line, font) <= max_width:
                    current_line.append(word)
                else:
                    final_lines.append(' '.join(current_line))
                    current_line = [word]
        
        if current_line:
            final_lines.append(' '.join(current_line))
    
    return final_lines if final_lines else ['']

# def generate_barcode(gtin):
    """Generate barcode image from GTIN"""
    try:
        # Determine barcode type based on GTIN length
        gtin = gtin.strip()
        if len(gtin) == 13:
            barcode_class = barcode.get_barcode_class('ean13')
        elif len(gtin) == 8:
            barcode_class = barcode.get_barcode_class('ean8')
        elif len(gtin) == 14:
            barcode_class = barcode.get_barcode_class('ean14')
        else:
            # Default to CODE128
            barcode_class = barcode.get_barcode_class('code128')
        
        # Generate barcode
        writer = ImageWriter()
        writer.set_options({
            'write_text': True,
            'font_size': 8,
            'module_height': 8,   # Reverted to a stable height; final scaling is now controlled in generate_label_image
            'module_width': 0.1  
        })
        
        barcode_instance = barcode_class(gtin, writer=writer)
        output = io.BytesIO()
        barcode_instance.write(output)
        output.seek(0)
        
        return Image.open(output)
    except Exception as e:
        print(f"Barcode generation error: {e}")
        return None

def create_zip_export(csv_upload):
    """Create ZIP file with all label images"""
    zip_path = os.path.join(settings.MEDIA_ROOT, f'export_{csv_upload.id}.zip')
    
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for label in csv_upload.labels.all():
            if label.image:
                # Convert to CMYK TIFF for print
                img = Image.open(label.image.path)
                cmyk_img = img.convert('CMYK')
                
                # Save as TIFF (supports CMYK)
                tiff_path = os.path.join(settings.MEDIA_ROOT, f'temp_label_{label.id}.tif')
                cmyk_img.save(tiff_path, format='TIFF', dpi=(300, 300))
                
                zipf.write(tiff_path, f'label_{label.product_code}.tif')
                
                # Clean up temp file
                os.remove(tiff_path)
    
    return zip_path

def create_pdf_export(csv_upload):
    """Create PDF with all label images"""
    pdf_path = os.path.join(settings.MEDIA_ROOT, f'export_{csv_upload.id}.pdf')
    
    c = canvas.Canvas(pdf_path, pagesize=letter)
    page_width, page_height = letter
    
    # Calculate positions for labels (2" x 3" at 72 DPI for PDF)
    label_width = 2 * 72  # 144 points
    label_height = 3 * 72  # 216 points
    
    x_margin = 36  # 0.5 inch margin
    y_margin = 36
    
    labels_per_row = int((page_width - 2 * x_margin) / label_width)
    labels_per_col = int((page_height - 2 * y_margin) / label_height)
    
    x_pos = x_margin
    y_pos = page_height - y_margin - label_height
    count = 0
    
    for label in csv_upload.labels.all():
        if label.image and os.path.exists(label.image.path):
            img = ImageReader(label.image.path)
            c.drawImage(img, x_pos, y_pos, width=label_width, height=label_height, preserveAspectRatio=True)
            
            count += 1
            x_pos += label_width
            
            if count % labels_per_row == 0:
                x_pos = x_margin
                y_pos -= label_height
                
                if count % (labels_per_row * labels_per_col) == 0 and count < csv_upload.labels.count():
                    c.showPage()
                    y_pos = page_height - y_margin - label_height
    
    c.save()
    return pdf_path
