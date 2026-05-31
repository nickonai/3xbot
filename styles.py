"""Каталог креативных стилей нейрофотосессий.

Каждый стиль содержит промпт для мужчины и для женщины. Промпты на английском
(gpt-image-2 точнее следует инструкциям на английском), описания — на русском
для меню в боте. Все промпты явно требуют сохранить лицо с входного фото.

Промпты подобраны исследованием актуальных трендов AI-фотосессий 2025-2026.
"""

# Порядок в списке = порядок и нумерация в меню бота.
STYLES = [
    {
        "id": "cinematic-noir",
        "emoji": "🎬",
        "title_ru": "Кинонуар",
        "desc_ru": "Чёрно-белый детектив 1940-х, жёсткие тени, дождь и неон.",
        "prompt_male": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; do not stylise or alter the face. Photorealistic black-and-white film noir portrait of the man in a rain-soaked alley, wearing a dark wool overcoat with a turned-up collar and a fedora, cigarette smoke curling through volumetric fog and neon reflections in the puddles. Shot on an 85mm portrait lens, shallow depth of field, hard single key light from the side creating dramatic chiaroscuro shadows, sharp focus on the eyes. Half-body framing at eye level, moody 1940s detective atmosphere, realistic skin texture with subtle film grain, no text in the image.",
        "prompt_female": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; do not stylise or alter the face. Photorealistic black-and-white film noir portrait of the woman in a rain-soaked alley, wearing a sleek belted trench coat and a vintage 1940s wave hairstyle, neon reflections in the puddles and volumetric fog drifting past. Shot on an 85mm portrait lens, shallow depth of field, dramatic hard side key light and deep chiaroscuro shadows, sharp focus on the eyes. Half-body framing at eye level, mysterious femme-fatale mood, realistic skin texture with subtle film grain, no text in the image.",
    },
    {
        "id": "cyberpunk-neon",
        "emoji": "🌃",
        "title_ru": "Киберпанк-неон",
        "desc_ru": "Футуристичный ночной город, неоновые розово-синие огни.",
        "prompt_male": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; do not cartoonise or alter the face. Photorealistic cyberpunk portrait of the man on a rainy neon-lit street in a futuristic 2090 city, wearing layered techwear with glowing LED accents and subtle holographic detailing, neon pink and electric-blue rim light wrapping his profile. Shot on an 85mm lens, shallow depth of field, neon rim light and wet reflective surfaces, sharp focus on the eyes. Half-body framing, low-angle, gritty high-tech mood, realistic skin texture with reflected neon on the cheeks, no text in the image.",
        "prompt_female": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; do not cartoonise or alter the face. Photorealistic cyberpunk portrait of the woman on a rainy neon-lit street in a futuristic 2090 city, wearing sleek glossy techwear with glowing LED trim and delicate holographic makeup, neon magenta and cyan rim light tracing her face. Shot on an 85mm lens, shallow depth of field, neon rim light against bokeh city lights, sharp focus on the eyes. Half-body framing, low-angle, edgy high-tech mood, realistic skin texture with reflected neon glow, no text in the image.",
    },
    {
        "id": "golden-hour",
        "emoji": "🌅",
        "title_ru": "Золотой час",
        "desc_ru": "Тёплый закатный портрет на открытом воздухе, мягкое сияние.",
        "prompt_male": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; do not alter the face. Photorealistic golden-hour outdoor portrait of the man in an open field at sunset, wearing a relaxed linen shirt or light knit with sleeves pushed up, warm sun flare grazing his jaw. Shot on an 85mm portrait lens, shallow depth of field, soft warm backlight with gentle rim glow on the hair, sharp focus on the eyes. Medium close-up at eye level, serene and warm mood, realistic skin texture with a sun-kissed glow, subtle film grain, no text in the image.",
        "prompt_female": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; do not alter the face. Photorealistic golden-hour outdoor portrait of the woman in an open field at sunset, wearing a flowing pastel dress with fabric and hair drifting in a soft breeze, warm sun flare wrapping around her. Shot on an 85mm portrait lens, shallow depth of field, dreamy warm backlight and soft glowing rim light, sharp focus on the eyes. Medium close-up at eye level, romantic and ethereal mood, realistic skin texture with a luminous sun-kissed glow, subtle film grain, no text in the image.",
    },
    {
        "id": "old-money",
        "emoji": "🏛️",
        "title_ru": "Old money",
        "desc_ru": "Тихая роскошь, поместье или яхт-клуб, приглушённая палитра.",
        "prompt_male": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; do not alter the face. Photorealistic old-money quiet-luxury portrait of the man at a country estate, wearing a tailored camel overcoat over a fine cable-knit sweater, muted earthy palette and refined posture. Shot on an 85mm portrait lens, shallow depth of field, soft natural daylight with gentle Rembrandt shaping, sharp focus on the eyes. Half-body framing, three-quarter view, understated wealthy and confident mood, realistic skin texture, no heavy retouching, no text in the image.",
        "prompt_female": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; do not alter the face. Photorealistic old-money quiet-luxury portrait of the woman at a country estate, wearing a tailored ivory coat over a cashmere knit with delicate gold jewellery, muted earthy palette and elegant poise. Shot on an 85mm portrait lens, shallow depth of field, soft natural daylight with gentle wrap, sharp focus on the eyes. Half-body framing, three-quarter view, refined and effortlessly elegant mood, realistic skin texture, no heavy retouching, no text in the image.",
    },
    {
        "id": "renaissance-oil",
        "emoji": "🖼️",
        "title_ru": "Ренессанс",
        "desc_ru": "Портрет в стиле старых мастеров, светотень, благородная поза.",
        "prompt_male": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; keep the face true to the photo. Classical Renaissance oil-painting portrait of the man rendered as a museum old-master work, wearing rich period drapery and a dark doublet, painterly brushwork and visible canvas texture. Dramatic Caravaggio chiaroscuro lighting with a single warm key emerging from deep shadow, head-and-shoulders composition, three-quarter noble pose. Gilded muted tones, dignified solemn mood, painted (not photographic) rendering, no text in the image.",
        "prompt_female": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; keep the face true to the photo. Classical Renaissance oil-painting portrait of the woman rendered as a museum old-master work, wearing rich velvet and silk period drapery with a delicate pearl detail, painterly brushwork and visible canvas texture. Soft Vermeer window light blending into chiaroscuro shadow, head-and-shoulders composition, graceful three-quarter pose. Gilded muted tones, serene noble mood, painted (not photographic) rendering, no text in the image.",
    },
    {
        "id": "action-figure",
        "emoji": "🧸",
        "title_ru": "Экшн-фигурка",
        "desc_ru": "Ты как коллекционная игрушка в блистерной упаковке.",
        "prompt_male": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; keep the sculpted figure's face an accurate likeness. Photorealistic product shot of the man as a collectible action figure sealed inside a plastic blister-pack on a cardboard backer, posed with themed accessories beside him in molded trays. The figure wears a detailed miniature outfit matching his style, glossy toy-plastic finish on the packaging. Shot on a 50mm lens, clean studio softbox lighting with crisp reflections on the blister plastic, sharp product focus, playful collectible mood, no text or logos in the image.",
        "prompt_female": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; keep the sculpted figure's face an accurate likeness. Photorealistic product shot of the woman as a collectible action figure sealed inside a plastic blister-pack on a cardboard backer, posed with themed accessories beside her in molded trays. The figure wears a detailed miniature outfit matching her style, glossy toy-plastic finish on the packaging. Shot on a 50mm lens, clean studio softbox lighting with crisp reflections on the blister plastic, sharp product focus, playful collectible mood, no text or logos in the image.",
    },
    {
        "id": "yearbook-90s",
        "emoji": "📼",
        "title_ru": "Школьный альбом 90-х",
        "desc_ru": "Ностальгическая зернистая плёнка, голубой фон, ретро-одежда.",
        "prompt_male": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; do not alter the face. Photorealistic 1990s high-school yearbook portrait of the man against a mottled blue laser studio backdrop, wearing a period-correct collared shirt or knit polo with a slightly dated haircut. Shot on grainy nostalgic film with soft flat studio lighting, slightly faded color balance, head-and-shoulders framing at eye level. Cheesy retro yearbook mood, visible film grain and gentle vignette, realistic skin texture, no text in the image.",
        "prompt_female": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; do not alter the face. Photorealistic 1990s high-school yearbook portrait of the woman against a mottled blue laser studio backdrop, wearing a period-correct blouse with voluminous 90s hairstyling. Shot on grainy nostalgic film with soft flat studio lighting, slightly faded color balance, head-and-shoulders framing at eye level. Charmingly dated retro yearbook mood, visible film grain and gentle vignette, realistic skin texture, no text in the image.",
    },
    {
        "id": "double-exposure",
        "emoji": "🌄",
        "title_ru": "Двойная экспозиция",
        "desc_ru": "Силуэт, внутри которого живёт целый пейзаж.",
        "prompt_male": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; the face must remain clearly recognizable. Artistic double-exposure portrait of the man: his profile silhouette is filled with an entire moody mountain landscape and stormy sky blended into the skin and hair. Clean light background, soft contrast, the secondary scene visible inside the darker tones of the face. 85mm portrait composition, head-and-shoulders, contemplative cinematic mood, crisp blend of photographic textures, no text in the image.",
        "prompt_female": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; the face must remain clearly recognizable. Artistic double-exposure portrait of the woman: her profile silhouette is filled with an entire dreamy forest-and-sunset landscape blended into the skin and flowing hair. Clean light background, soft contrast, the secondary scene visible inside the darker tones of the face. 85mm portrait composition, head-and-shoulders, poetic cinematic mood, crisp blend of photographic textures, no text in the image.",
    },
    {
        "id": "gatsby-1920s",
        "emoji": "🥂",
        "title_ru": "Гэтсби, 1920-е",
        "desc_ru": "Роскошный бальный зал, ар-деко, тёплое золотое сияние.",
        "prompt_male": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; do not alter the face. Photorealistic 1920s Great Gatsby portrait of the man in a sharp black tuxedo with a bow tie and slicked-back hair, standing in an opulent art-deco ballroom with vintage chandeliers. Shot on an 85mm lens, shallow depth of field, warm golden ambient glow with soft key light, sharp focus on the eyes. Half-body framing, confident roaring-twenties glamour mood, realistic skin texture, subtle film grain, no text in the image.",
        "prompt_female": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; do not alter the face. Photorealistic 1920s Great Gatsby portrait of the woman in a beaded sequined flapper dress with a feathered headband and finger-wave hairstyle, standing in an opulent art-deco ballroom with vintage chandeliers. Shot on an 85mm lens, shallow depth of field, warm golden ambient glow with soft glamour key light, sharp focus on the eyes. Half-body framing, dazzling roaring-twenties glamour mood, realistic skin texture, subtle film grain, no text in the image.",
    },
    {
        "id": "editorial-glamour",
        "emoji": "✨",
        "title_ru": "Глянец / эдиториал",
        "desc_ru": "Обложка журнала, студийный свет, безупречный стиль.",
        "prompt_male": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; do not alter the face. Photorealistic high-fashion editorial portrait of the man styled for a magazine cover, wearing a sharply tailored designer suit against a clean seamless studio backdrop. Shot on an 85mm lens, large softbox key at 45 degrees with a rim accent light for a chiseled jawline, razor-sharp focus on the eyes. Half-body framing, confident editorial-cool mood, realistic skin texture with visible pores and no plastic smoothing, glossy high-end fashion aesthetic, no text in the image.",
        "prompt_female": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; do not alter the face. Photorealistic high-fashion editorial beauty portrait of the woman styled for a magazine cover, wearing elegant designer couture against a clean seamless studio backdrop. Shot on an 85mm lens, soft diffused glamour key with a delicate rim light, razor-sharp focus on the eyes. Half-body framing, polished glamorous editorial mood, realistic luminous skin texture with subtle natural detail, glossy high-end fashion aesthetic, no text in the image.",
    },
    {
        "id": "corporate-headshot",
        "emoji": "💼",
        "title_ru": "Корпоративный портрет",
        "desc_ru": "Чистый деловой хедшот для LinkedIn и резюме.",
        "prompt_male": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; do not alter the face. Photorealistic professional corporate headshot of the man wearing a well-fitted navy blazer over a crisp shirt, against a softly blurred modern office or neutral gray studio background. Shot on an 85mm portrait lens, shallow depth of field, soft even key light with gentle fill and clean shadow edges, sharp focus on the eyes. Head-and-shoulders framing at eye level, approachable and confident professional mood, realistic skin texture, no heavy retouching, no text in the image.",
        "prompt_female": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; do not alter the face. Photorealistic professional corporate headshot of the woman wearing a tailored blazer over a simple top, against a softly blurred modern office or neutral gray studio background. Shot on an 85mm portrait lens, shallow depth of field, soft even key light with gentle fill and clean shadow edges, sharp focus on the eyes. Head-and-shoulders framing at eye level, approachable and confident professional mood, realistic skin texture, no heavy retouching, no text in the image.",
    },
    {
        "id": "fantasy-fae",
        "emoji": "🧝",
        "title_ru": "Фэнтези / эльф",
        "desc_ru": "Заколдованный лес, эфирные одежды, магическое свечение.",
        "prompt_male": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; keep the face fully recognizable, only add subtly pointed ears. Photorealistic fantasy portrait of the man as an elven warrior in an enchanted misty forest, wearing ornate engraved leather-and-metal armor with a flowing cloak, faint magical glow drifting through the trees. Shot on an 85mm lens, shallow depth of field, soft ethereal key light with a cool rim glow, sharp focus on the eyes. Half-body framing, noble and otherworldly mood, realistic skin texture, cinematic fantasy atmosphere, no text in the image.",
        "prompt_female": "Use the person in the input image as the subject reference and preserve their facial identity, face shape, and features exactly; keep the face fully recognizable, only add subtly pointed ears. Photorealistic fantasy portrait of the woman as an elven princess in an enchanted misty forest, wearing a flowing ethereal gown with delicate silver filigree and a thin circlet, faint magical glow and floating light particles around her. Shot on an 85mm lens, shallow depth of field, soft dreamy key light with a luminous rim glow, sharp focus on the eyes. Half-body framing, graceful and otherworldly mood, realistic skin texture, cinematic fantasy atmosphere, no text in the image.",
    },
]


def get_style(style_id: str):
    """Стиль по id или None."""
    for s in STYLES:
        if s["id"] == style_id:
            return s
    return None


def prompt_for(style: dict, gender: str) -> str:
    """Промпт под пол ('male'/'female'); по умолчанию мужской."""
    return style["prompt_female"] if gender == "female" else style["prompt_male"]
