// Pure data module (server-safe — no React, no 'use client'). The client-only
// rotation hook lives in components/discover/TrendingCarousel.tsx.

export interface DiscoverTopic {
  /** URL slug → /topic/[slug]. Kebab-case, stable. */
  slug: string
  /** Carousel card + landing-page H1. */
  title: string
  /** Short overlay line on the carousel card (≈4–7 words). */
  hook: string
  /** Eyebrow / grouping label. */
  category: string
  /** Card + landing hero image (must exist under public/images). */
  image: string
  /** Research query seeded into chat from the landing-page CTA. */
  query: string
  /** Editorial intro shown on the landing page (1–2 sentences). */
  blurb: string
}

// ── Pool of ~50 curated Discover topics ─────────────────────────────────────
// Each card is browse-only: clicking opens its /topic/[slug] landing page (NOT
// a chat preload). The "into research" CTA lives on the landing page.
// Images are REUSED from public/images/{browse,categories,products,travel}.
// Terracotta tokens only — never the legacy blue icon pastels.
export const DISCOVER_TOPICS: DiscoverTopic[] = [
  // Audio
  { slug: 'noise-cancelling-headphones', title: 'Best Noise-Cancelling Headphones', hook: 'Silence the world, keep the music', category: 'Audio', image: '/images/categories/cat-headphones.webp', query: 'Best noise-cancelling headphones 2026', blurb: 'The best ANC cans now disappear on your head and erase the engine drone of a flight. We line up the picks worth their price — and the sleepers that punch above it.' },
  { slug: 'wireless-earbuds', title: 'Wireless Earbuds Worth It', hook: 'Tiny buds, big sound', category: 'Audio', image: '/images/products/mosaic-headphones.webp', query: 'Best wireless earbuds under $150', blurb: 'Great earbuds are no longer a luxury — the sweet spot under $150 is stacked. Here is who nails sound, fit, and battery without the flagship tax.' },
  { slug: 'bluetooth-speakers', title: 'Bluetooth Speakers That Slap', hook: 'Backyard-to-beach sound', category: 'Audio', image: '/images/products/mosaic-speaker.webp', query: 'Best portable Bluetooth speakers 2026', blurb: 'One speaker, every setting — picnic, shower, tailgate. We rank the portables that go loud, take a splash, and last all day.' },
  { slug: 'home-audio-setup', title: 'Build a Home Audio Setup', hook: 'Fill the room, not the budget', category: 'Audio', image: '/images/categories/cat-audio.webp', query: 'Best home audio speakers and soundbars 2026', blurb: 'Better sound at home is mostly about buying smart, not spending big. We map the soundbars and bookshelf speakers that transform a room.' },

  // Computing
  { slug: 'student-laptops', title: 'Laptops for Students', hook: 'Light bag, long battery', category: 'Computing', image: '/images/categories/cat-laptops.webp', query: 'Best laptops for students 2026', blurb: 'The right student laptop survives a full day of classes and a backpack full of abuse. These are the ones that balance weight, battery, and price.' },
  { slug: 'creator-laptops', title: 'Laptops for Creators', hook: 'Render, edit, repeat', category: 'Computing', image: '/images/products/mosaic-laptop.webp', query: 'Best laptops for video editing and design 2026', blurb: 'Editing 4K and exporting on deadline needs real silicon, not marketing. Here are the creator machines that keep the timeline scrubbing smooth.' },
  { slug: 'budget-laptops', title: 'Best Laptops Under $700', hook: 'Real value, no compromises', category: 'Computing', image: '/images/categories/cat-laptops.webp', query: 'Best budget laptops under $700', blurb: 'You can get a genuinely good laptop for under $700 — if you know where the corners are cut. We sort the bargains from the regrets.' },
  { slug: 'macbook-vs-windows', title: 'MacBook vs Windows', hook: 'Settle the debate', category: 'Computing', image: '/images/products/mosaic-laptop.webp', query: 'MacBook Air vs Windows laptop — which should I buy', blurb: 'The honest answer depends on what you actually do all day. We break down where each platform wins so you stop second-guessing the purchase.' },
  { slug: 'tablets', title: 'Tablets for Work & Play', hook: 'Laptop-light, couch-ready', category: 'Computing', image: '/images/categories/cat-laptops.webp', query: 'Best tablets 2026', blurb: 'A tablet can replace your laptop — or just be the best couch screen you own. We match the right slab to how you’ll really use it.' },

  // Phones
  { slug: 'flagship-phones', title: 'Flagship Phones 2026', hook: 'The best glass money buys', category: 'Phones', image: '/images/categories/cat-smartphones.webp', query: 'Best flagship smartphones 2026', blurb: 'Every flagship claims to be the best — the cameras and battery tell the truth. Here’s where the top phones actually pull ahead.' },
  { slug: 'budget-phones', title: 'Best Cheap Phones', hook: 'Premium feel, friendly price', category: 'Phones', image: '/images/categories/cat-smartphones.webp', query: 'Best budget smartphones under $400', blurb: 'Sub-$400 phones have quietly gotten great. We spotlight the ones that feel twice their price and skip the ones that cut the wrong corners.' },
  { slug: 'camera-phones', title: 'Phones for Photographers', hook: 'Pocket cameras that text', category: 'Phones', image: '/images/categories/cat-smartphones.webp', query: 'Best camera phones 2026', blurb: 'The best camera is the one in your pocket — so make it a good one. These phones turn everyday moments into keepers.' },

  // Smart home
  { slug: 'smart-home-starter', title: 'Smart Home Starter Kit', hook: 'Automate the basics under $200', category: 'Smart Home', image: '/images/categories/cat-smart-home.webp', query: 'Smart home starter kit under $200', blurb: 'You don’t need to rewire the house to feel the magic. Start with a few smart picks that pay off the first week — all for under $200.' },
  { slug: 'robot-vacuums', title: 'Robot Vacuums, Ranked', hook: 'Never sweep again', category: 'Smart Home', image: '/images/browse/home-appliances.jpg', query: 'Best robot vacuums for pet hair', blurb: 'The good robovacs map your home, dodge the cat, and empty themselves. We rank the ones that actually clean versus the ones that just bump around.' },
  { slug: 'video-doorbells', title: 'Best Video Doorbells', hook: 'See who’s at the door', category: 'Smart Home', image: '/images/browse/smart-home.jpg', query: 'Best video doorbells 2026', blurb: 'A doorbell cam is the cheapest peace of mind you can buy. Here’s who balances sharp video, smart alerts, and fair subscription terms.' },
  { slug: 'smart-thermostats', title: 'Smart Thermostats', hook: 'Lower bills, cozy home', category: 'Smart Home', image: '/images/categories/cat-smart-home.webp', query: 'Best smart thermostats to save energy', blurb: 'A smart thermostat learns your schedule and trims the bill while you’re out. We pick the ones that pay for themselves fastest.' },

  // Kitchen
  { slug: 'espresso-machines', title: 'Espresso at Home', hook: 'Café shots, kitchen counter', category: 'Kitchen', image: '/images/products/mosaic-espresso.webp', query: 'Best home espresso machines for beginners', blurb: 'That daily café habit adds up fast — a home machine pays for itself by spring. We find the beginner-friendly picks that still pull a serious shot.' },
  { slug: 'air-fryers', title: 'Air Fryers Worth the Counter', hook: 'Crispy, fast, guilt-free', category: 'Kitchen', image: '/images/categories/cat-kitchen.webp', query: 'Best air fryers 2026', blurb: 'The right air fryer earns its counter space every single night. We rank them on crisp, capacity, and how little you’ll dread cleaning them.' },
  { slug: 'blenders', title: 'Blenders That Actually Blend', hook: 'Smoothies to soups', category: 'Kitchen', image: '/images/categories/cat-kitchen.webp', query: 'Best blenders for smoothies', blurb: 'A cheap blender turns kale into chunks; a good one turns it into silk. Here’s where to spend — and where you really don’t need to.' },
  { slug: 'coffee-makers', title: 'Best Coffee Makers', hook: 'Wake up to better coffee', category: 'Kitchen', image: '/images/products/mosaic-espresso.webp', query: 'Best drip coffee makers 2026', blurb: 'Better mornings start with a better brewer. We line up the drip machines that nail temperature, flavor, and a no-fuss routine.' },

  // Fitness
  { slug: 'running-shoes', title: 'Running Shoes, Ranked', hook: 'Trail to treadmill', category: 'Fitness', image: '/images/products/mosaic-sneakers.webp', query: 'Best running shoes 2026', blurb: 'The right shoe is the difference between loving and dreading the run. We match cushioning, drop, and durability to how and where you log miles.' },
  { slug: 'fitness-smartwatches', title: 'Smartwatches & Trackers', hook: 'Your wrist, your coach', category: 'Fitness', image: '/images/products/mosaic-smartwatch.webp', query: 'Best fitness smartwatches 2026', blurb: 'A good tracker turns vague goals into streaks you actually keep. Here’s who nails accuracy, battery, and the features you’ll really use.' },
  { slug: 'home-gym', title: 'Build a Home Gym', hook: 'Gains without the membership', category: 'Fitness', image: '/images/products/mosaic-fitness-gear.webp', query: 'Best home gym equipment on a budget', blurb: 'A corner of the garage beats a membership you skip. We pick the versatile gear that builds a full workout without filling the room.' },
  { slug: 'exercise-bikes', title: 'Peloton vs The Rest', hook: 'Spin smarter, spend less', category: 'Fitness', image: '/images/categories/cat-fitness.webp', query: 'Peloton vs cheaper exercise bikes', blurb: 'The bike is only half the cost — the classes are the rest. We compare Peloton against the challengers so you don’t overpay for the logo.' },

  // Cameras
  { slug: 'mirrorless-cameras', title: 'Mirrorless Cameras', hook: 'Pro shots, lighter kit', category: 'Cameras', image: '/images/products/mosaic-camera.webp', query: 'Best mirrorless cameras for beginners', blurb: 'Mirrorless gives you DSLR quality in half the bag. We pick the bodies that grow with you instead of boxing you in.' },
  { slug: 'vlogging-gear', title: 'Vlogging Starter Gear', hook: 'Press record, go viral', category: 'Cameras', image: '/images/categories/cat-cameras.webp', query: 'Best vlogging cameras and gear 2026', blurb: 'Good content is mostly good audio and a camera that flips around. Here’s the starter kit that punches way above its follower count.' },
  { slug: 'action-cameras', title: 'Action Cameras', hook: 'Capture the chaos', category: 'Cameras', image: '/images/categories/cat-cameras.webp', query: 'Best action cameras for adventure', blurb: 'Mud, surf, snow — an action cam shrugs it all off. We rank stabilization, mounts, and battery for the days worth filming.' },

  // Gaming
  { slug: 'gaming-laptops', title: 'Gaming Laptops', hook: 'Frames on the go', category: 'Gaming', image: '/images/categories/cat-gaming.webp', query: 'Best gaming laptops 2026', blurb: 'A gaming laptop is a balancing act of frames, heat, and battery. We find the machines that run hot games cool — and don’t sound like a jet.' },
  { slug: 'gaming-headsets', title: 'Gaming Headsets', hook: 'Hear them first', category: 'Gaming', image: '/images/categories/cat-gaming.webp', query: 'Best gaming headsets 2026', blurb: 'Positional audio wins rounds and a comfy headset wins marathons. Here’s who delivers both without the wallet damage.' },
  { slug: 'game-consoles', title: 'Which Console to Buy', hook: 'PlayStation, Xbox, or Switch', category: 'Gaming', image: '/images/categories/cat-gaming.webp', query: 'Which game console should I buy in 2026', blurb: 'The right console is the one with the games you want and the friends you play with. We break down the trade-offs so you pick once and play.' },

  // Fashion
  { slug: 'everyday-sneakers', title: 'Everyday Sneakers', hook: 'Comfy enough to live in', category: 'Fashion', image: '/images/products/mosaic-sneakers.webp', query: 'Best everyday sneakers 2026', blurb: 'The best everyday sneaker goes with everything and feels like nothing. We sort the all-day comfort picks from the fashion-only ones.' },
  { slug: 'winter-coats', title: 'Winter Coats That Last', hook: 'Warm, not bulky', category: 'Fashion', image: '/images/categories/cat-fashion.webp', query: 'Best winter coats 2026', blurb: 'A great coat is warmth you don’t have to think about for years. Here’s where the warmth-to-weight math actually works out.' },
  { slug: 'work-bags', title: 'Work Bags & Backpacks', hook: 'Carry it all in style', category: 'Fashion', image: '/images/browse/fashion-style.jpg', query: 'Best work backpacks and laptop bags 2026', blurb: 'The right bag protects your laptop and your back without looking like a gym sack. We pick the carry that survives the commute in style.' },

  // Beauty
  { slug: 'skincare-starter', title: 'Skincare That Works', hook: 'Glow on a budget', category: 'Beauty', image: '/images/categories/cat-beauty.webp', query: 'Best skincare starter routine 2026', blurb: 'A great routine is three good products, not thirty. We cut through the hype to the budget picks dermatologists actually rate.' },
  { slug: 'hair-tools', title: 'Hair Tools Worth Buying', hook: 'Salon results at home', category: 'Beauty', image: '/images/categories/cat-beauty.webp', query: 'Best hair dryers and stylers 2026', blurb: 'The right tool cuts your routine in half and saves your strands. Here’s where the premium price pays off — and where it doesn’t.' },

  // Outdoor
  { slug: 'camping-gear', title: 'Camping Gear Essentials', hook: 'Sleep under the stars', category: 'Outdoor', image: '/images/categories/cat-outdoor.webp', query: 'Best camping gear for beginners', blurb: 'A good first kit makes the difference between “again next weekend” and “never again.” We pick the tent-to-sleeping-bag essentials that earn their pack weight.' },
  { slug: 'hiking-boots', title: 'Hiking Boots, Tested', hook: 'Miles of comfort', category: 'Outdoor', image: '/images/browse/outdoor-fitness.jpg', query: 'Best hiking boots 2026', blurb: 'Blisters end a hike faster than weather. We rank the boots that grip, breathe, and break in before they break you.' },

  // Home & furniture
  { slug: 'office-chairs', title: 'Office Chairs for Your Back', hook: 'Sit all day, pain-free', category: 'Home Office', image: '/images/categories/cat-furniture.webp', query: 'Best ergonomic office chairs 2026', blurb: 'You spend more hours in your chair than your bed — buy accordingly. We pick the ergonomic seats that keep your lower back happy at hour eight.' },
  { slug: 'mattresses', title: 'Mattresses for Better Sleep', hook: 'Wake up actually rested', category: 'Home', image: '/images/categories/cat-home-decor.webp', query: 'Best mattresses for back pain', blurb: 'The right mattress is the cheapest health upgrade you’ll make. We match firmness and feel to how you sleep — and to back pain that won’t quit.' },
  { slug: 'standing-desks', title: 'Standing Desks', hook: 'Work on your feet', category: 'Home Office', image: '/images/categories/cat-furniture.webp', query: 'Best standing desks 2026', blurb: 'A stable, quiet standing desk changes how a workday feels. We pick the ones that lift smoothly and don’t wobble at standing height.' },
  { slug: '4k-tvs', title: '4K TVs Without the Markup', hook: 'Cinema on your wall', category: 'Home Theater', image: '/images/browse/electronics.jpg', query: 'Best 4K TVs under $700', blurb: 'You don’t need to spend four figures for a stunning picture. We find the under-$700 sets that look like they cost twice as much.' },
  { slug: 'air-purifiers', title: 'Air Purifiers for Allergies', hook: 'Breathe easier at home', category: 'Home', image: '/images/browse/health-wellness.jpg', query: 'Best air purifiers for allergies', blurb: 'The right purifier quietly pulls pollen and dust out of the room you sleep in. We rank them on real-room performance, noise, and filter cost.' },

  // Family
  { slug: 'baby-gear', title: 'New-Parent Essentials', hook: 'Less guesswork, more sleep', category: 'Family', image: '/images/browse/baby.jpg', query: 'Best baby gear essentials for new parents', blurb: 'Every list says you need everything — you don’t. We cut the registry down to the gear that genuinely earns its keep in the first year.' },
  { slug: 'kids-tech', title: 'Tech for Kids', hook: 'Screen time, done right', category: 'Family', image: '/images/browse/kids-toys.jpg', query: 'Best educational tech and toys for kids', blurb: 'The best kids’ tech teaches something and survives a toddler. We pick the tablets, toys, and tools worth the shelf space.' },

  // Travel
  { slug: 'tokyo-guide', title: 'Tokyo Travel Guide', hook: 'Neon nights, hidden alleys', category: 'Travel', image: '/images/travel/hero-asia.webp', query: 'Tokyo travel guide — flights, hotels, hidden gems', blurb: 'Tokyo rewards the curious — the best of it is down side streets, not in guidebooks. We map the flights, stays, and neighborhoods worth your days.' },
  { slug: 'europe-by-rail', title: 'Europe by Rail', hook: 'City-hop the continent', category: 'Travel', image: '/images/travel/hero-europe.webp', query: 'Plan a Europe rail trip itinerary', blurb: 'Trains turn Europe into one walkable city after another. We help you chain the route, passes, and stops into a trip that actually flows.' },
  { slug: 'caribbean-escape', title: 'Caribbean Escapes', hook: 'Sun, sand, repeat', category: 'Travel', image: '/images/travel/hero-caribbean.webp', query: 'Best Caribbean vacation destinations', blurb: 'Every island has a personality — the trick is matching it to your kind of trip. We line up the beaches, resorts, and timing that fit the escape you want.' },
  { slug: 'cheap-flights', title: 'Score Cheap Flights', hook: 'Fly more, pay less', category: 'Travel', image: '/images/travel/hero-flight.webp', query: 'How to find the cheapest flights', blurb: 'The cheapest seat is rarely the one you see first. We share the timing, tools, and tricks that quietly knock hundreds off a fare.' },
  { slug: 'mountain-getaways', title: 'Mountain Getaways', hook: 'Trade traffic for trails', category: 'Travel', image: '/images/travel/hero-mountains.webp', query: 'Best mountain vacation destinations', blurb: 'Altitude has a way of resetting everything. We pick the mountain towns and trails worth the drive, in every season.' },
  { slug: 'boutique-hotels', title: 'Boutique Hotels Worth It', hook: 'Stays you’ll brag about', category: 'Travel', image: '/images/travel/hero-hotel.webp', query: 'Best boutique hotels for a weekend getaway', blurb: 'A great hotel is half the trip. We find the boutique stays with character — the ones that make the weekend feel like a story.' },
]

/** Lookup a topic by slug (for the /topic/[slug] landing page). */
export function getTopicBySlug(slug: string): DiscoverTopic | undefined {
  return DISCOVER_TOPICS.find((t) => t.slug === slug)
}
