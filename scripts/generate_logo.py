#!/usr/bin/env python3
from PIL import Image, ImageDraw, ImageFont
import os

def create_logo():
    # Ukuran gambar
    size = (512, 512)
    padding = 80
    
    # Buat gambar baru dengan background transparan
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Warna hijau untuk Qt
    qt_green = (0, 157, 89, 255)  # Warna hijau Qt yang profesional
    
    # Gambar lingkaran luar (border)
    circle_bbox = (padding, padding, size[0]-padding, size[1]-padding)
    draw.ellipse(circle_bbox, fill=(40, 40, 40, 255))
    
    # Gambar lingkaran dalam (background)
    inner_padding = padding + 10
    inner_circle = (inner_padding, inner_padding, 
                   size[0]-inner_padding, size[1]-inner_padding)
    draw.ellipse(inner_circle, fill=(20, 20, 20, 255))
    
    # Gambar pedang silang
    sword_width = 30
    sword_length = 280
    center_x = size[0] // 2
    center_y = size[1] // 2
    
    # Pedang 1 (diagonal kiri atas ke kanan bawah)
    points1 = [
        (center_x - sword_length//2, center_y - sword_length//2),
        (center_x - sword_length//2 + sword_width, center_y - sword_length//2),
        (center_x + sword_length//2, center_y + sword_length//2 - sword_width),
        (center_x + sword_length//2, center_y + sword_length//2),
    ]
    
    # Pedang 2 (diagonal kanan atas ke kiri bawah)
    points2 = [
        (center_x + sword_length//2, center_y - sword_length//2),
        (center_x + sword_length//2, center_y - sword_length//2 + sword_width),
        (center_x - sword_length//2, center_y + sword_length//2),
        (center_x - sword_length//2, center_y + sword_length//2 - sword_width),
    ]
    
    # Gambar pedang dengan warna putih
    draw.polygon(points1, fill='white')
    draw.polygon(points2, fill='white')
    
    # Tambahkan teks "Qt" dengan warna hijau
    try:
        # Coba load font Ubuntu
        font = ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-Bold.ttf", 120)
    except:
        try:
            # Coba load font DejaVu Sans
            font = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", 120)
        except:
            # Fallback ke default font
            font = ImageFont.load_default()
    
    # Posisi teks Qt
    text = "Qt"
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    text_x = center_x - text_width//2
    text_y = center_y + sword_length//4
    
    # Gambar teks Qt dengan warna hijau
    draw.text((text_x, text_y), text, font=font, fill=qt_green)
    
    # Simpan gambar
    img.save('tuxcut.png', 'PNG')

if __name__ == '__main__':
    create_logo() 