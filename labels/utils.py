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
    """Process CSV file and create ProductLabel instances"""
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
        try:
            encoder = 'cp1252'
            with open(file_path, mode='r', encoding=encoder) as f:
                reader = csv.DictReader(f)
                print(f"Testing ecoder withv{encoder} for Product: {next(reader).get('ProductName')}")
                # Delete existing labels for this upload
                csv_upload.labels.all().delete()
            
        except:
            encoder = 'utf-8'
            with open(file_path, mode='r', encoding=encoder) as f:
                reader = csv.DictReader(f)
                print(f"Testing ecoder withv{encoder} for Product: {next(reader).get('ProductName')}")
        with open(file_path, mode='r', encoding=encoder) as f:
            print("opened csv")
            reader = csv.DictReader(f)
            for row in reader:
                print(row.get('ProductName'))
                label = ProductLabel.objects.create(
                    csv_upload=csv_upload,
                    product_name=row.get('ProductName', ''),
                    mrp=row.get('MRP', ''),
                    quality=row.get('Quality', ''),
                    size=row.get('Size', ''),
                    net_quantity=row.get('Net Quantity', ''),
                    product_code=row.get('Product Code', ''),
                    design_color=row.get('Design / Color', ''),
                    mfg_month='',
                    mfg_year='',
                    gtin=row.get('GTINs', ''),
                    manufacturer=manufacturer_text
                )
                
                # Parse Mth & Year of Mfg. column
                mfg_date = row.get('Mth & Year of Mfg.', '')
                if mfg_date:
                    label.mfg_month = mfg_date.split()[0] if mfg_date.split() else ''
                    label.mfg_year = mfg_date.split()[1] if len(mfg_date.split()) > 1 else ''
                    label.save()
                
                # Generate label image
                image_file = generate_label_image(label)
                label.image.save(f'label_{label.id}.png', image_file, save=True)
    except Exception as e:
        print(f"Couldn't complete label creation. error: {e}")
    csv_upload.processed = True
    csv_upload.save()

def generate_label_image(label):
    """Generate label image with specifications, improved margins, and bold labels."""
    # Image dimensions: 2 inches x 3 inches at 300 DPI
    dpi = 300
    width = int(2 * dpi)  # 600 pixels
    height = int(3 * dpi)  # 900 pixels
    
    # Create RGB image
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Define the font color
    FONT_COLOR = '#816457'
    
    # Border and padding
    border_width = 2
    border_padding_offset = 15  # 5px padding inside the image for the border rectangle itself (Margin from image edge)
    padding = 20  # Content padding inside the border (Margin from border) - Increased from 20 to 30 for increased top/bottom margin
    
    # Draw border (offset by 5 pixels from the image edge)
    draw.rectangle(
        [(border_padding_offset, border_padding_offset), 
         (width - border_padding_offset, height - border_padding_offset)],
        outline=FONT_COLOR,
        width=border_width
    )

    # Font setup - Myriad Pro 6.5pt at 300 DPI
    # The standard calculation for 6.5pt at 300DPI (approx 27px) was visually too large.
    # A reduction factor (0.9) is applied to fine-tune the visual size while keeping the 6.5pt base.
    target_point_size = 6.5
    visual_reduction_factor = 0.9 
    
    calculated_pixel_size = target_point_size * dpi / 72
    font_size = int(calculated_pixel_size * visual_reduction_factor) # New effective size is approx 24 pixels
    
    # Ensure a minimum size
    if font_size < 10: 
        font_size = 10 # Set a sensible minimum if calculation results in a tiny size
    
    # Variables to track font paths (for MII font creation)
    bold_font_path = None

    try:
        # Load custom Myriad Pro fonts from the static directory structure
        font_dir = os.path.join(settings.BASE_DIR, 'static', 'style', 'fonts', 'myriad-pro')
        
        regular_font_path = os.path.join(font_dir, 'MYRIADPRO-REGULAR.OTF')
        bold_font_path = os.path.join(font_dir, 'MYRIADPRO-BOLD.OTF')
        
        font_normal = ImageFont.truetype(regular_font_path, font_size)
        font_bold = ImageFont.truetype(bold_font_path, font_size)
        
        print(f"INFO: Successfully loaded custom fonts (Myriad Pro) from: {font_dir}")
        
    except Exception as e:
        # Fallback to default font if custom fonts cannot be loaded (e.g., path error)
        print(f"WARNING: Failed to load custom font files from {font_dir}.")
        print(f"Exception details: {e}")
        print("Falling back to default PIL font.")
        
        font_size = 18
        font_normal = ImageFont.load_default()
        font_bold = ImageFont.load_default()
    
    # Starting position (initial margin for content: border offset + border width + content padding)
    x = border_padding_offset + border_width + padding
    y = border_padding_offset + border_width + padding
    # Line height uses the calculated (and possibly reduced) font_size
    line_height = int(font_size * 1.3) # Base line height

    # --- START OF CELL PADDING CHANGE (Request 1) ---
    # Explicit padding/gap added after each table row.
    row_padding = line_height // 3 # New explicit row gap (~33% of line height)
    # --- END OF CELL PADDING CHANGE ---

    
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
    
    # Calculate table width (available width minus padding)
    table_width = width - 2 * x # Use the computed x value for the total left/right content margin
    label_column_width = int(table_width * 0.4)  # 40% for labels
    # Position for the value column, with a small gap after the label column
    value_column_x = x + label_column_width + 8 
    
    # Draw table
    for field_label, field_value in table_data:
        # Draw label (bold) in first column (as requested)
        draw.text((x, y), field_label, font=font_bold, fill=FONT_COLOR)
        
        # Calculate max width for the value column
        max_value_width = table_width - label_column_width - 8
        
        # Wrap value text if it's too long
        value_lines = wrap_text(field_value, font_normal, max_value_width)
        for i, value_line in enumerate(value_lines):
            draw.text((value_column_x, y + (i * line_height)), value_line, font=font_normal, fill=FONT_COLOR)
        
        # Move down for the next row, based on how many lines the value took
        y += line_height * max(1, len(value_lines))
        # Add the explicit padding/gap between rows (Request 1)
        y += row_padding

    # --- START OF SPACE BETWEEN TABLE AND MANUFACTURER (Request 2) ---
    # Add some spacing. Changed from line_height // 2 to a larger value (1.5x)
    y += int(line_height * 1.1)
    # --- END OF SPACE CHANGE ---
    
    # Manufacturer info
    draw.text((x, y), 'Manufactured and Marketed By :', font=font_bold, fill=FONT_COLOR)
    y += line_height
    
    # Split manufacturer text by lines (respecting explicit line breaks)
    manufacturer_parts = label.manufacturer.split('\n')
    for part in manufacturer_parts:
        # Wrap each part if it's too long
        wrapped_lines = wrap_text(part, font_normal, width - 2 * x) # Use 2*x for total margin
        for line in wrapped_lines:
            draw.text((x, y), line, font=font_normal, fill=FONT_COLOR)
            y += line_height
    
    # Add spacing after manufacturer text. This is the starting point for the barcode/MII block.
    y += line_height // 2 
    y_barcode_block_start = y
    
    # --- 1. Prepare "Make in India" text properties (Pinned to the very bottom) ---
    mii_text = "Make in India"
    
    # Use a slightly larger font for emphasis (e.g., 20% larger than base)
    mii_font_size = int(font_size * 1.2)
    font_make_in_india = font_bold
    
    # Re-attempt loading the slightly larger bold font
    try:
        if bold_font_path and os.path.exists(bold_font_path):
            font_make_in_india = ImageFont.truetype(bold_font_path, mii_font_size)
    except Exception:
        pass # Use existing font_bold instance if custom font fails

    # Calculate MII text width and approximate height
    mii_width = draw.textlength(mii_text, font=font_make_in_india)
    mii_text_height = mii_font_size + (line_height // 4) # Font size plus a small buffer
    x_mii_centered = (width - mii_width) / 2

    # Bottom boundary of the label content area (inner padding)
    bottom_content_y = height - (border_padding_offset + border_width + padding)
    
    # Calculate Y position for the MII text (pinned to the bottom)
    y_mii_start = bottom_content_y - mii_text_height
    
    # Barcode max height must end at the start of the MII text area
    barcode_available_height = y_mii_start - y_barcode_block_start

    # NEW: Control the barcode's final height by targeting a percentage of the available space
    BARCODE_TARGET_HEIGHT_RATIO = 1 
    barcode_target_height = int(barcode_available_height * BARCODE_TARGET_HEIGHT_RATIO)
    
    # --- 2. Generate and Draw Barcode (above MII text) ---
    if label.gtin and barcode_target_height > 0:
        barcode_img = generate_barcode(label.gtin)
        
        if barcode_img:
            if barcode_img.mode != 'RGB':
                barcode_img = barcode_img.convert('RGB')
            
            # Available horizontal space for the barcode
            barcode_max_width = width - 2 * x 
            
            # Calculate height if scaled to max width (maintaining aspect ratio)
            ratio = barcode_img.width / barcode_img.height
            
            final_width = barcode_max_width
            final_height = int(final_width / ratio)

            # Use the newly calculated target height for constraint
            max_allowed_height = barcode_target_height

            # If the calculated height is too large, constrain by max_allowed_height and re-calculate width
            if final_height > max_allowed_height:
                final_height = max_allowed_height
                final_width = int(final_height * ratio)

            # Ensure we have non-zero dimensions
            if final_width > 0 and final_height > 0:
                barcode_img = barcode_img.resize((final_width, final_height), Image.Resampling.LANCZOS)
                
                # Center the barcode horizontally
                x_centered = x + (barcode_max_width - final_width) // 2
                
                # Center the barcode vertically in the *available* reserved space
                reserved_space_height = y_mii_start - y_barcode_block_start
                vertical_padding = (reserved_space_height - final_height) // 2
                y_barcode_paste = y_barcode_block_start + vertical_padding
                
                img.paste(barcode_img, (x_centered, y_barcode_paste))
    
    # --- 3. Draw "Make in India" text (at the bottom reserved spot) ---
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

def generate_barcode(gtin):
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
