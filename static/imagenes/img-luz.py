from PIL import Image, ImageFilter, ImageOps
import numpy as np

# Cargar la imagen original
img = Image.open('logo2.png').convert("RGBA")

# Crear un lienzo más grande para que quepa el resplandor y la sombra
border = 40
new_size = (img.width + border * 2, img.height + border * 2)

# 1. Crear la capa de RESPLANDOR (Backlight)
# Extraemos el canal alfa para tener la silueta
alpha = img.getchannel('A')
glow_mask = Image.new("L", new_size, 0)
glow_mask.paste(alpha, (border, border))

# Desenfocar la silueta para el resplandor
glow = glow_mask.filter(ImageFilter.GaussianBlur(radius=15))
# Crear una imagen blanca con esa máscara de resplandor (luz blanca reflejada)
backlight = Image.new("RGBA", new_size, (255, 255, 255, 0))
glow_colored = Image.new("RGBA", new_size, (255, 255, 255, 120)) # Luz blanca suave
backlight.paste(glow_colored, (0, 0), mask=glow)

# 2. Crear la capa de SOMBRA (para el efecto de separación de 3cm)
shadow_mask = Image.new("L", new_size, 0)
shadow_mask.paste(alpha, (border + 5, border + 5)) # Desplazada un poco
shadow_blur = shadow_mask.filter(ImageFilter.GaussianBlur(radius=10))
shadow = Image.new("RGBA", new_size, (0, 0, 0, 80)) # Sombra tenue

# 3. Combinar todo\nfinal_img = Image.new("RGBA", new_size, (0, 0, 0, 0))
final_img.paste(shadow, (0, 0), mask=shadow_blur) # Primero sombra
final_img.paste(backlight, (0, 0), mask=glow) # Luego el brillo
final_img.paste(img, (border, border), mask=img) # Finalmente el logo original

final_img.save('logo_egalvez_3d_effect.png')
print("Imagen procesada guardada como logo_egalvez_3d_effect.png")
