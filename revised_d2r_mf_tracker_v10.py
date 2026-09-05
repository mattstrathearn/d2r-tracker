#!/usr/bin/env python3
"""
D2R MF Run Tracker — fixed-size overlay
- Borderless main window and borderless stats window
- Alt+1 start/stop run, Alt+2 focus item entry, Alt+3 open stats
- Optional global hotkeys with `keyboard`
- Run type + P1-P8 tracking
- Item autocomplete list baked in from the uploaded unique/set/misc files
"""

import json
import os
import sqlite3
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

try:
    import keyboard as kb
    GLOBAL_HOTKEYS = True
except ImportError:
    GLOBAL_HOTKEYS = False

try:
    import d2r_vision as vision
    import d2r_autodetect
    VISION_MODULE = True
except ImportError:
    vision = None
    d2r_autodetect = None
    VISION_MODULE = False

DIFFICULTIES = ["Hell", "NM", "Normal"]

# Screen-reading defaults. Regions stay None until the user calibrates them;
# everything else is tuned for 1920x1080 and adjustable from the Auto-Detect
# settings window.
DEFAULT_AUTO_SETTINGS = {
    "enabled": False,
    "difficulty": "Hell",
    "loading_region": None,
    "area_region": None,
    "dark_threshold": 22,
    "dark_samples": 2,
    "poll_interval": 0.25,
    "area_poll_interval": 1.5,
    "area_settle_delay": 0.6,
    "area_tolerance": 90,
    "area_min_score": 80,
    "area_miss_limit": 3,
    "fallback_without_area": True,
    "stop_in_town": True,
    "restart_on_area_change": False,
    "min_run_seconds": 3.0,
    "tooltip_width": 460,
    "tooltip_height": 130,
    "tooltip_offset_x": 0,
    "tooltip_offset_y": 0,
    "tooltip_tolerance": 60,
    "item_min_score": 75,
    "capture_qualities": ["unique", "set", "rune"],
    "tesseract_path": "",
}

RUN_TYPES = [
    "Hell - Countess",
    "Hell - The Pit",
    "Hell - Andariel",
    "Hell - Ancient Tunnels",
    "Hell - Arcane Sanctuary",
    "Hell - Summoner",
    "Hell - Travincal",
    "Hell - Mephisto",
    "Hell - Chaos Sanctuary",
    "Hell - Diablo",
    "Hell - Shenk / Eldritch",
    "Hell - Pindleskin",
    "Hell - Nihlathak",
    "Hell - Worldstone Keep",
    "Hell - Baal",
    "Hell - Cows",
    "Hell - Lower Kurast",
    "Hell - Stony Tomb",
    "Hell - Arachnid Lair",
    "Hell - Maggot Lair",
    "Hell - River of Flame",
    "Hell - Frigid Highlands",
    "NM - Countess",
    "NM - Andariel",
    "NM - Mephisto",
    "NM - Diablo",
    "NM - Baal",
    "NM - Chaos Sanctuary",
    "NM - Travincal",
    "NM - Cows",
    "Normal - Andariel",
    "Normal - Mephisto",
    "Normal - Diablo",
    "Normal - Baal",
    "Normal - Cows",
    "Uber Tristram",
    "Uber Diablo (DClone)",
    "Pandemonium Event"
]
PLAYER_COUNTS = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8"]
D2R_ITEMS = [
    "A Jade Figurine [misc]",
    "Aldur's Advance [set #69]",
    "Aldur's Deception [set #67]",
    "Aldur's Gauntlet [set #68]",
    "Aldur's Stony Gaze [set #66]",
    "Alma Negra [unique #329]",
    "Amethyst [misc]",
    "Amn Rune [misc]",
    "Amulet [misc]",
    "Amulet of the Viper [misc]",
    "Amulet of the Viper [unique #123]",
    "Andariel's Visage [unique #345]",
    "Angelic Halo [set #52]",
    "Angelic Mantle [set #51]",
    "Angelic Sickle [set #50]",
    "Angelic Wings [set #53]",
    "Annihilus [unique #381]",
    "Antidote Potion [misc]",
    "Arachnid Mesh [unique #373]",
    "Arcanna's Deathwand [set #59]",
    "Arcanna's Flesh [set #61]",
    "Arcanna's Head [set #60]",
    "Arcanna's Sign [set #58]",
    "Arctic Binding [set #56]",
    "Arctic Furs [set #55]",
    "Arctic Horn [set #54]",
    "Arctic Mitts [set #57]",
    "Arioc's Needle [unique #382]",
    "Arkaine's Valor [unique #251]",
    "Arm of King Leoric [unique #141]",
    "Armor [unique]",
    "Arreat's Face [unique #279]",
    "Arrows [misc]",
    "Ars Al'Diablolos [unique #408]",
    "Ars Dul'Mephistos [unique #410]",
    "Ars Tor'Baalos [unique #409]",
    "Athena's Wrath [unique #179]",
    "Atma's Scarab [unique #273]",
    "Atma's Wail [unique #220]",
    "Azurewrath [unique #29]",
    "Azurewrath [unique #301]",
    "Baal's Eye [misc]",
    "Baezil's Vortex [unique #150]",
    "Bane Ash [unique #54]",
    "Bane's Authority [set #134]",
    "Bane's Oathmaker [set #132]",
    "Bane's Wraithskin [set #133]",
    "Baranar's Star [unique #256]",
    "Ber Rune [misc]",
    "Berserker's Hatchet [set #46]",
    "Berserker's Hauberk [set #45]",
    "Berserker's Headgear [set #44]",
    "Bing Sz Wang [unique #163]",
    "Black Cleft [unique #406]",
    "Black Hades [unique #221]",
    "Blackbog's Sharp [unique #170]",
    "Blackhand Key [unique #142]",
    "Blackhorn's Face [unique #207]",
    "Blackleach Blade [unique #178]",
    "Blackoak Shield [unique #252]",
    "Blacktongue [unique #36]",
    "Blade of Ali Baba [unique #157]",
    "Bladebone [unique #2]",
    "Bladebuckle [unique #116]",
    "Blastbark [unique #66]",
    "Blinkbats Form [unique #80]",
    "Blood Crescent [unique #26]",
    "Bloodfist [unique #103]",
    "Bloodletter [unique #154]",
    "Bloodmoon [unique #289]",
    "Bloodpact Shard [unique #414]",
    "Bloodraven's Charge [unique #332]",
    "Bloodrise [unique #20]",
    "Bloodthief [unique #45]",
    "Bloodtree Stump [unique #152]",
    "Bolts [misc]",
    "Bone Break [unique #405]",
    "Boneflame [unique #341]",
    "Boneflesh [unique #88]",
    "Bonehew [unique #387]",
    "Boneshade [unique #351]",
    "Boneslayer Blade [unique #137]",
    "Bonesob [unique #23]",
    "Book of Skill [misc]",
    "Brain [misc]",
    "Brainhew [unique #8]",
    "Bul Katho's Wedding Band [unique #268]",
    "Bul-Kathos' Sacred Charge [set #115]",
    "Bul-Kathos' Tribal Guardian [set #116]",
    "Buriza-Do Kyanon [unique #198]",
    "Burning Essence of Terror [misc]",
    "Butcher's Pupil [unique #130]",
    "Bverrit Keep [unique #100]",
    "Carin Shard [unique #140]",
    "Carrion Wind [unique #378]",
    "Cathan's Mesh [set #26]",
    "Cathan's Rule [set #25]",
    "Cathan's Seal [set #29]",
    "Cathan's Sigil [set #28]",
    "Cathan's Visage [set #27]",
    "Cerebus [unique #310]",
    "Cham Rune [misc]",
    "Chance Guards [unique #104]",
    "Charged Essense of Hatred [misc]",
    "Chipped Amethyst [misc]",
    "Chipped Diamond [misc]",
    "Chipped Emerald [misc]",
    "Chipped Ruby [misc]",
    "Chipped Sapphire [misc]",
    "Chipped Skull [misc]",
    "Chipped Topaz [misc]",
    "Chromatic Ire [unique #185]",
    "Civerb's Cudgel [set #2]",
    "Civerb's Icon [set #1]",
    "Civerb's Ward [set #0]",
    "Class Specific [unique]",
    "Cleglaw's Claw [set #7]",
    "Cleglaw's Pincers [set #8]",
    "Cleglaw's Tooth [set #6]",
    "Cliffkiller [unique #193]",
    "Cloudcrack [unique #165]",
    "Coif of Glory [unique #73]",
    "Cold Rupture [unique #401]",
    "Coldkill [unique #129]",
    "Coldsteel Eye [unique #155]",
    "Colossal Jewel [misc]",
    "Constricting Ring [unique #263]",
    "Corpsemourn [unique #222]",
    "Cow King's Hide [set #118]",
    "Cow King's Hoofs [set #119]",
    "Cow King's Horns [set #117]",
    "Crack of the Heavens [unique #403]",
    "Crafted Black Cleft [unique #437]",
    "Crafted Bone Break [unique #436]",
    "Crafted Cold Rupture [unique #427]",
    "Crafted Crack of the Heavens [unique #434]",
    "Crafted Flame Rift [unique #433]",
    "Crafted Rotting Fissure [unique #435]",
    "Crafted Sunder Charm [misc]",
    "Crainte Vomir [unique #162]",
    "Cranebeak [unique #383]",
    "Credendum [set #99]",
    "Crescent Moon [unique #271]",
    "Crow Caw [unique #214]",
    "Crown of Ages [unique #344]",
    "Crown of Thieves [unique #206]",
    "Crushflange [unique #19]",
    "Culwens Point [unique #32]",
    "Cutthroat1 [unique #286]",
    "Dangoon's Teaching [set #100]",
    "Dark Clan Crusher [unique #143]",
    "Darkfear [unique #346]",
    "Darkforge Spawn [unique #330]",
    "Darkglow [unique #83]",
    "Darksight Helm [unique #204]",
    "Death's Guard [set #48]",
    "Death's Hand [set #47]",
    "Death's Touch [set #49]",
    "Deathbit [unique #291]",
    "Deathcleaver [unique #314]",
    "Deaths's Web [unique #299]",
    "Deathspade [unique #1]",
    "Deep Worldstone Shard [misc]",
    "Defender's Bile [unique #420]",
    "Defender's Fire [unique #423]",
    "Demon Machine [unique #199]",
    "Demon's Arch [unique #340]",
    "Demonhorn's Edge [unique #325]",
    "Demonlimb [unique #296]",
    "Diablo's Horn [misc]",
    "Diamond [misc]",
    "Dimoaks Hew [unique #48]",
    "Djinnslayer [unique #290]",
    "Dol Rune [misc]",
    "Doombringer [unique #260]",
    "Doomspittle [unique #70]",
    "Dracul's Grasp [unique #364]",
    "Dragonscale [unique #347]",
    "Dreadfang [unique #412]",
    "Duriel's Shell [unique #216]",
    "Duskdeep [unique #74]",
    "Dwarf Star [unique #274]",
    "Eaglehorn [unique #265]",
    "Ear [misc]",
    "Earthshaker [unique #151]",
    "Earthshifter [unique #385]",
    "Eastern Worldstone Shard [misc]",
    "El Rune [misc]",
    "Eld Rune [misc]",
    "Elite Uniques [unique]",
    "Elixir [misc]",
    "Emerald [misc]",
    "Endlesshail [unique #191]",
    "Entropy Locket [unique #417]",
    "Eschuta's temper [unique #367]",
    "Eth Rune [misc]",
    "Ethereal Edge [unique #324]",
    "Executioner's Justice [unique #315]",
    "Eye [misc]",
    "Fal Rune [misc]",
    "Fang [misc]",
    "Fathom [unique #354]",
    "Fechmars Axe [unique #5]",
    "Felloak [unique #14]",
    "Festering Essence of Destruction [misc]",
    "Firelizard's Talons [unique #368]",
    "Flag [misc]",
    "Flame Rift [unique #402]",
    "Flamebellow [unique #353]",
    "Flawed Amethyst [misc]",
    "Flawed Diamond [misc]",
    "Flawed Emerald [misc]",
    "Flawed Ruby [misc]",
    "Flawed Sapphire [misc]",
    "Flawed Skull [misc]",
    "Flawed Topaz [misc]",
    "Flawless Amethyst [misc]",
    "Flawless Diamond [misc]",
    "Flawless Emerald [misc]",
    "Flawless Ruby [misc]",
    "Flawless Sapphire [misc]",
    "Flawless Skull [misc]",
    "Flawless Topaz [misc]",
    "Fleshrender [unique #147]",
    "Fleshripper [unique #304]",
    "Frostburn [unique #106]",
    "Frostwind [unique #365]",
    "Full Healing Potion [misc]",
    "Full Mana Potion [misc]",
    "Full Rejuvenation Potion [misc]",
    "Gargoyle's Bite [unique #320]",
    "Gheed's Fortune [unique #359]",
    "Gheed's Wager [unique #418]",
    "Ghostflame [unique #333]",
    "Ghoulhide [unique #234]",
    "Giantmaimer [unique #339]",
    "Giantskull [unique #379]",
    "Gimmershred [unique #335]",
    "Ginther's Rift [unique #158]",
    "Gleamscythe [unique #28]",
    "Gloomstrap [unique #244]",
    "Goblin Toe [unique #110]",
    "Godstrike Arch [unique #195]",
    "Gold [misc]",
    "Goldskin [unique #91]",
    "Goldwrap [unique #115]",
    "Gore Ripper [unique #295]",
    "Gorefoot [unique #108]",
    "Gorerider [unique #241]",
    "Goreshovel [unique #6]",
    "Grand Charm [misc]",
    "Gravenspine [unique #12]",
    "Gravepalm [unique #233]",
    "Greater Healing Potion [misc]",
    "Greater Mana Potion [misc]",
    "Greyform [unique #79]",
    "Griffon's Eye [unique #336]",
    "Grim's Burning Dead [unique #182]",
    "Griswold's Heart [set #82]",
    "Griswold's Honor [set #84]",
    "Griswold's Valor [set #81]",
    "Griswolds Edge [unique #30]",
    "Griswolds's Redemption [set #83]",
    "Guardian Angel [unique #218]",
    "Guardian Naga [unique #133]",
    "Guardian's Light [unique #425]",
    "Guardian's Thunder [unique #421]",
    "Guillaume's Face [set #104]",
    "Gul Rune [misc]",
    "Gull [unique #39]",
    "Gutsiphon [unique #293]",
    "Haemosu's Adament [set #102]",
    "Halaberd's Reign [unique #361]",
    "Hand of Blessed Light [unique #146]",
    "Harlequin Crest [unique #248]",
    "Hawkmail [unique #84]",
    "Headhunter's Glory [unique #390]",
    "Headstriker [unique #159]",
    "Healing Potion [misc]",
    "Heart [misc]",
    "Heart Carver [unique #169]",
    "Heaven's Light [unique #371]",
    "Heaven's Taebaek [set #101]",
    "Heavenly Garb [unique #93]",
    "Hel Rune [misc]",
    "Hell Forge Hammer [unique #126]",
    "Hellcast [unique #69]",
    "Hellclap [unique #65]",
    "Hellfire Torch [unique #400]",
    "Hellmouth [unique #236]",
    "Hellplague [unique #31]",
    "Hellrack [unique #328]",
    "Hellslayer [unique #254]",
    "Herald of Zakarum [unique #285]",
    "Herb [misc]",
    "Hexfire [unique #156]",
    "Highlord's Wrath [unique #276]",
    "Homunculus [unique #280]",
    "Hone Sundan [unique #175]",
    "Horadric Cube [misc]",
    "Horadric Scroll [misc]",
    "Horadric Staff [unique #125]",
    "Horazon's Countenance [set #135]",
    "Horazon's Dominion [set #136]",
    "Horazon's Hold [set #137]",
    "Horazon's Legacy [set #138]",
    "Horazon's Secrets [set #139]",
    "Horizon's Tornado [unique #306]",
    "Horn [misc]",
    "Hotspur [unique #107]",
    "Howltusk [unique #76]",
    "Hsarus' Iron Fist [set #4]",
    "Hsarus' Iron Heel [set #3]",
    "Hsarus' Iron Stay [set #5]",
    "Husoldal Evo [unique #181]",
    "Hwanin's Justice [set #111]",
    "Hwanin's Refuge [set #109]",
    "Hwanin's Seal [set #110]",
    "Hwanin's Splendor [set #108]",
    "Iceblink [unique #87]",
    "Ichorsting [unique #68]",
    "Immortal King's Detail [set #72]",
    "Immortal King's Forge [set #73]",
    "Immortal King's Pillar [set #74]",
    "Immortal King's Soul Cage [set #71]",
    "Immortal King's Stone Crusher [set #75]",
    "Immortal King's Will [set #70]",
    "Infernal Cranium [set #41]",
    "Infernal Sign [set #43]",
    "Infernal Torch [set #42]",
    "Infernostride [unique #237]",
    "Io Rune [misc]",
    "Iratha's Coil [set #11]",
    "Iratha's Collar [set #9]",
    "Iratha's Cord [set #12]",
    "Iratha's Cuff [set #10]",
    "Irices Shard [unique #42]",
    "Ironpelt [unique #212]",
    "Ironstone [unique #22]",
    "Ironward [unique #380]",
    "Iros Torch [unique #10]",
    "Isenhart's Case [set #15]",
    "Isenhart's Horns [set #16]",
    "Isenhart's Lightbrand [set #13]",
    "Isenhart's Parry [set #14]",
    "Islestrike [unique #131]",
    "Ist Rune [misc]",
    "Ith Rune [misc]",
    "Jadetalon [unique #308]",
    "Jah Rune [misc]",
    "Jalal's Mane [unique #287]",
    "Jawbone [misc]",
    "Jewel [misc]",
    "Kelpie Snare [unique #173]",
    "Kerke's Sanctuary [unique #228]",
    "Key [misc]",
    "Key of Destruction [misc]",
    "Key of Hate [misc]",
    "Key of Terror [misc]",
    "Key to the Cairn Stones [misc]",
    "Khalim's Brain [misc]",
    "Khalim's Eye [misc]",
    "Khalim's Heart [misc]",
    "KhalimFlail [unique #127]",
    "Kinemils Awl [unique #35]",
    "Kira's Guardian [unique #357]",
    "Knell Striker [unique #15]",
    "Ko Rune [misc]",
    "Krintizs Skewer [unique #27]",
    "Kuko Shakaku [unique #190]",
    "Lacerator [unique #321]",
    "Lam Esen's Tome [misc]",
    "Lance Guard [unique #231]",
    "Lance of Yaggai [unique #46]",
    "Langer Briser [unique #196]",
    "Large Blue Potion [misc]",
    "Large Charm [misc]",
    "Large Red Potion [misc]",
    "Larzuk's Champion [unique #318]",
    "Lavagout [unique #235]",
    "Laying of Hands [set #96]",
    "Lazarus Spire [unique #56]",
    "Leadcrow [unique #67]",
    "Lem Rune [misc]",
    "Lenyms Cord [unique #112]",
    "Leviathan [unique #317]",
    "Lidless Wall [unique #230]",
    "Light Healing Potion [misc]",
    "Light Mana Potion [misc]",
    "Lightsabre [unique #259]",
    "Lo Rune [misc]",
    "Lum Rune [misc]",
    "Lycander's Aim [unique #282]",
    "Lycander's Flank [unique #283]",
    "M'avina's Caster [set #94]",
    "M'avina's Embrace [set #91]",
    "M'avina's Icy Clutch [set #92]",
    "M'avina's Tenet [set #93]",
    "M'avina's True Sight [set #90]",
    "Maelstromwrath [unique #11]",
    "Magefist [unique #105]",
    "Magewrath [unique #194]",
    "Magnus' Skin [set #106]",
    "Mal Rune [misc]",
    "Malah's Potion [misc]",
    "Mana Potion [misc]",
    "Manald Heal [unique #121]",
    "Mang Song's Lesson [unique #322]",
    "Mara's Kaleidoscope [unique #272]",
    "Marrowwalk [unique #370]",
    "McAuley's Paragon [set #123]",
    "McAuley's Riprap [set #124]",
    "McAuley's Superstition [set #126]",
    "McAuley's Taboo [set #125]",
    "Measured Wrath [unique #411]",
    "Medusa's Gaze [unique #349]",
    "Mephisto's Brain [misc]",
    "Mephisto's Soulstone [misc]",
    "Merman's Speed [unique #372]",
    "Messerschmidt's Reaver [unique #255]",
    "Metalgrid [unique #375]",
    "Milabrega's Diadem [set #23]",
    "Milabrega's Orb [set #21]",
    "Milabrega's Robe [set #24]",
    "Milabrega's Rod [set #22]",
    "Mindrend [unique #3]",
    "Minor Healing Potion [misc]",
    "Minor Mana Potion [misc]",
    "Moonfall [unique #149]",
    "Mosers Blessed Circle [unique #225]",
    "Nagelring [unique #120]",
    "Naj's Circlet [set #122]",
    "Naj's Light Plate [set #121]",
    "Naj's Puzzler [set #120]",
    "Natalya's Mark [set #63]",
    "Natalya's Shadow [set #64]",
    "Natalya's Soul [set #65]",
    "Natalya's Totem [set #62]",
    "Nature's Peace [unique #300]",
    "Nef Rune [misc]",
    "Nethercrow [unique #352]",
    "Nightsmoke [unique #114]",
    "Nightwing's Veil [unique #343]",
    "Nokozan Relic [unique #117]",
    "Nord's Tenderizer [unique #384]",
    "Northern Worldstone Shard [misc]",
    "Nosferatu's Coil [unique #374]",
    "Odium [unique #305]",
    "Ohm Rune [misc]",
    "Ondal's Almighty [set #103]",
    "Ondal's Wisdom [unique #388]",
    "Opalvein [unique #416]",
    "Ormus' Robes [unique #358]",
    "Ort Rune [misc]",
    "Peasent Crown [unique #201]",
    "Pelta Lunata [unique #94]",
    "Perfect Amethyst [misc]",
    "Perfect Diamond [misc]",
    "Perfect Emerald [misc]",
    "Perfect Ruby [misc]",
    "Perfect Sapphire [misc]",
    "Perfect Skull [misc]",
    "Perfect Topaz [misc]",
    "Piercerib [unique #62]",
    "Pierre Tombale Couant [unique #180]",
    "Plague Bearer [unique #160]",
    "Pluckeye [unique #59]",
    "Pompe's Wrath [unique #132]",
    "Potion of Life [misc]",
    "PreCrafted Black Cleft [unique #432]",
    "PreCrafted Bone Break [unique #431]",
    "PreCrafted Cold Rupture [unique #426]",
    "PreCrafted Crack of the Heavens [unique #429]",
    "PreCrafted Flame Rift [unique #428]",
    "PreCrafted Rotting Fissure [unique #430]",
    "Protector's Frost [unique #422]",
    "Protector's Stone [unique #424]",
    "Pul Rune [misc]",
    "Pullspite [unique #63]",
    "Pus Spiter [unique #197]",
    "Que-Hegan's Wisdon [unique #223]",
    "Quill [misc]",
    "Radimant's Sphere [unique #229]",
    "Rainbow Facet [unique #392]",
    "Rainbow Facet [unique #393]",
    "Rainbow Facet [unique #394]",
    "Rainbow Facet [unique #395]",
    "Rainbow Facet [unique #396]",
    "Rainbow Facet [unique #397]",
    "Rainbow Facet [unique #398]",
    "Rainbow Facet [unique #399]",
    "Rakescar [unique #4]",
    "Ral Rune [misc]",
    "Rattlecage [unique #90]",
    "Raven Frost [unique #275]",
    "Ravenlore [unique #350]",
    "Razoredge [unique #294]",
    "Razorswitch [unique #183]",
    "Razortail [unique #243]",
    "Razortine [unique #44]",
    "Rejuvenation Potion [misc]",
    "Ribcracker [unique #184]",
    "Rimeraven [unique #61]",
    "Ring [misc]",
    "Rings [unique]",
    "Riphook [unique #189]",
    "Ripsaw [unique #37]",
    "Rite of Passage [set #97]",
    "Rixots Keen [unique #25]",
    "Rockfleece [unique #89]",
    "Rockstopper [unique #202]",
    "Rotting Fissure [unique #404]",
    "Ruby [misc]",
    "Runemaster [unique #313]",
    "Rusthandle [unique #16]",
    "Sandstorm Trek [unique #369]",
    "Sapphire [misc]",
    "Saracen's Chance [unique #277]",
    "Sazabi's Cobalt Redeemer [set #112]",
    "Sazabi's Ghost Liberator [set #113]",
    "Sazabi's Mental Sheath [set #114]",
    "Scalp [misc]",
    "Schaefer's Hammer [unique #257]",
    "Scroll of Identify [misc]",
    "Scroll of Inifuss [misc]",
    "Scroll of Knowledge [misc]",
    "Scroll of Resistance [misc]",
    "Scroll of Town Portal [misc]",
    "Seraph's Hymn [unique #302]",
    "Serpent Lord [unique #55]",
    "Shadowdancer [unique #309]",
    "Shadowfang [unique #33]",
    "Shadowkiller [unique #334]",
    "Shael Rune [misc]",
    "Shaftstop [unique #215]",
    "Sigon's Gage [set #35]",
    "Sigon's Guard [set #40]",
    "Sigon's Sabot [set #38]",
    "Sigon's Shelter [set #37]",
    "Sigon's Visor [set #36]",
    "Sigon's Wrap [set #39]",
    "Sigurd's Staunch [unique #377]",
    "Silkweave [unique #239]",
    "Skin of the Flayerd One [unique #211]",
    "Skin of the Vipermagi [unique #210]",
    "Skull [misc]",
    "Skullcollector [unique #187]",
    "Skullder's Ire [unique #217]",
    "Skystrike [unique #188]",
    "Sling [unique #415]",
    "Small Blue Potion [misc]",
    "Small Charm [misc]",
    "Small Red Potion [misc]",
    "Snakecord [unique #113]",
    "Snowclash [unique #245]",
    "Sol Rune [misc]",
    "Soul [misc]",
    "Soul Harvest [unique #50]",
    "Souldrain [unique #312]",
    "Soulfeast Tine [unique #174]",
    "Soulflay [unique #34]",
    "Southern Worldstone Shard [misc]",
    "Sparking Mail [unique #85]",
    "Spellsteel [unique #135]",
    "Spike Thorn [unique #363]",
    "Spineripper [unique #168]",
    "Spire of Honor [unique #176]",
    "Spirit Ward [unique #356]",
    "Spiritforge [unique #213]",
    "Spiritkeeper [unique #327]",
    "Spiritual Custodian [set #98]",
    "Spleen [misc]",
    "Staff of Kings [unique #124]",
    "Stamina Potion [misc]",
    "Standard of Heroes [misc]",
    "Stealskull [unique #203]",
    "Steel Carapice [unique #348]",
    "Steelclash [unique #99]",
    "Steeldriver [unique #24]",
    "Steelgoad [unique #49]",
    "Steelpillar [unique #342]",
    "Steelrend [unique #391]",
    "Steelshade [unique #297]",
    "Stone Crusher [unique #307]",
    "Stoneraven [unique #316]",
    "Stormchaser [unique #226]",
    "Stormeye [unique #17]",
    "Stormguild [unique #96]",
    "Stormlash [unique #360]",
    "Stormrider [unique #136]",
    "Stormshield [unique #253]",
    "Stormspike [unique #171]",
    "Stormspire [unique #264]",
    "Stoutnail [unique #18]",
    "String of Ears [unique #242]",
    "Suicide Branch [unique #139]",
    "Super Healing Potion [misc]",
    "Super Mana Potion [misc]",
    "SuperKhalimFlail [unique #128]",
    "Sur Rune [misc]",
    "Sureshrill Frost [unique #148]",
    "Swordback Hold [unique #98]",
    "Swordguard [unique #167]",
    "Tail [misc]",
    "Tal Rasha's Adjudication [set #77]",
    "Tal Rasha's Fire-Spun Cloth [set #76]",
    "Tal Rasha's Horadric Crest [set #80]",
    "Tal Rasha's Howling Wind [set #79]",
    "Tal Rasha's Lidless Eye [set #78]",
    "Tal Rune [misc]",
    "Tancred's Crowbill [set #30]",
    "Tancred's Hobnails [set #32]",
    "Tancred's Skull [set #34]",
    "Tancred's Spine [set #31]",
    "Tancred's Weird [set #33]",
    "Tarnhelm [unique #72]",
    "Tearhaunch [unique #111]",
    "Telling of Beads [set #95]",
    "Templar's Might [unique #366]",
    "Thawing Potion [misc]",
    "The Atlantian [unique #161]",
    "The Battlebranch [unique #51]",
    "The Black Tower Key [misc]",
    "The Cat's Eye [unique #269]",
    "The Centurion [unique #81]",
    "The Chieftan [unique #7]",
    "The Cranium Basher [unique #258]",
    "The Diggler [unique #40]",
    "The Dragon Chang [unique #43]",
    "The Eye of Etlich [unique #118]",
    "The Face of Horror [unique #78]",
    "The Fetid Sprinkler [unique #145]",
    "The Gavel of Pain [unique #153]",
    "The Generals Tan Do Li Ga [unique #21]",
    "The Gladiator's Bane [unique #250]",
    "The Gnasher [unique #0]",
    "The Golden Bird [misc]",
    "The Grandfather [unique #261]",
    "The Grim Reaper [unique #53]",
    "The Hand of Broc [unique #102]",
    "The Humongous [unique #9]",
    "The Impaler [unique #172]",
    "The Iron Jang Bong [unique #58]",
    "The Jade Tan Do [unique #41]",
    "The Mahim-Oak Curio [unique #119]",
    "The Meat Scraper [unique #177]",
    "The Minataur [unique #138]",
    "The Oculus [unique #284]",
    "The Patriarch [unique #38]",
    "The Reaper's Toll [unique #326]",
    "The Reedeemer [unique #389]",
    "The Rising Sun [unique #270]",
    "The Salamander [unique #57]",
    "The Scalper [unique #288]",
    "The Spirit Shroud [unique #209]",
    "The Stone of Jordan [unique #122]",
    "The Tannr Gorerod [unique #47]",
    "The Vile Husk [unique #164]",
    "The Ward [unique #101]",
    "Thudergod's Vigor [unique #246]",
    "Thul Rune [misc]",
    "Thunderstroke [unique #338]",
    "Tiamat's Rebuke [unique #227]",
    "Tir Rune [misc]",
    "Titan's Revenge [unique #281]",
    "Todesfaelle Flamme [unique #166]",
    "Token of Absolution [misc]",
    "Tomb Reaver [unique #298]",
    "Tome of Identify [misc]",
    "Tome of Town Portal [misc]",
    "Toothrow [unique #219]",
    "Topaz [misc]",
    "Torch [misc]",
    "Trang-Oul's Claws [set #88]",
    "Trang-Oul's Girth [set #89]",
    "Trang-Oul's Guise [set #85]",
    "Trang-Oul's Scales [set #86]",
    "Trang-Oul's Wing [set #87]",
    "Treads of Cthon [unique #109]",
    "Twisted Essence of Suffering [misc]",
    "Twitchthroe [unique #82]",
    "Tyrael's Might [unique #311]",
    "Uber Ancient Summon Material Act 1 [misc]",
    "Uber Ancient Summon Material Act 2 [misc]",
    "Uber Ancient Summon Material Act 3 [misc]",
    "Uber Ancient Summon Material Act 4 [misc]",
    "Uber Ancient Summon Material Act5 [misc]",
    "Uber Ancient Upgrade Material  Cold [misc]",
    "Uber Ancient Upgrade Material  Fire [misc]",
    "Uber Ancient Upgrade Material Lightning [misc]",
    "Uber Ancient Upgrade Material Magic [misc]",
    "Uber Ancient Upgrade Material Physical [misc]",
    "Uber Ancient Upgrade Material Poison [misc]",
    "Um Rune [misc]",
    "Umbral Disk [unique #95]",
    "Umes Lament [unique #13]",
    "Undead Crown [unique #77]",
    "Unique Warlock Helm [unique #419]",
    "Valkiry Wing [unique #205]",
    "Vampiregaze [unique #208]",
    "Veil of Steel [unique #249]",
    "Venom Grip [unique #232]",
    "Venomsward [unique #86]",
    "Verdugo's Hearty Cord [unique #376]",
    "Vex Rune [misc]",
    "Victors Silk [unique #92]",
    "Vidala's Ambush [set #19]",
    "Vidala's Barb [set #17]",
    "Vidala's Fetlock [set #18]",
    "Vidala's Snare [set #20]",
    "Viperfork [unique #323]",
    "Visceratuant [unique #224]",
    "Wall of the Eyeless [unique #97]",
    "War Bonnet [unique #71]",
    "Warlock Class Pack [unique]",
    "Warlord's Authority [set #131]",
    "Warlord's Conquest [set #127]",
    "Warlord's Crushers [set #130]",
    "Warlord's Lust [set #128]",
    "Warlord's Mantle [set #129]",
    "Warlord's Trust [unique #134]",
    "Warpspear [unique #186]",
    "Warriv's Warder [unique #362]",
    "Warshrike [unique #292]",
    "Wartraveler [unique #240]",
    "Waterwalk [unique #238]",
    "Western Worldstone Shard [misc]",
    "Whichwild String [unique #192]",
    "Widowmaker [unique #331]",
    "Wihtstan's Guard [set #107]",
    "Wilhelm's Pride [set #105]",
    "Windforce [unique #266]",
    "Windhammer [unique #337]",
    "Wisp [unique #319]",
    "Witherstring [unique #60]",
    "Wizardspike [unique #262]",
    "Wizendraw [unique #64]",
    "Woestave [unique #52]",
    "Wolfhowl [unique #355]",
    "Wormskull [unique #75]",
    "Wraithflight [unique #386]",
    "Wraithstep [unique #413]",
    "Zakarum's Hand [unique #144]",
    "Zakarum's Salvation [unique #303]",
    "Zod Rune [misc]"
]


class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()
        self._migrate_runs_table()

    def _create_tables(self):
        c = self.conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_name TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                run_type TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_seconds REAL,
                player_count TEXT NOT NULL DEFAULT 'P1',
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                found_time TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(id)
            )
            """
        )
        self.conn.commit()

    def _migrate_runs_table(self):
        cols = {row["name"] for row in self.conn.execute("PRAGMA table_info(runs)")}
        if "player_count" not in cols:
            self.conn.execute("ALTER TABLE runs ADD COLUMN player_count TEXT NOT NULL DEFAULT 'P1'")
            self.conn.commit()
        self.conn.execute("UPDATE runs SET player_count = 'P1' WHERE player_count IS NULL OR TRIM(player_count) = ''")
        self.conn.commit()

    def start_session(self, character_name):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO sessions (character_name, start_time) VALUES (?, ?)",
            (character_name, datetime.now().isoformat()),
        )
        self.conn.commit()
        return cur.lastrowid

    def end_session(self, session_id):
        self.conn.execute(
            "UPDATE sessions SET end_time = ? WHERE id = ?",
            (datetime.now().isoformat(), session_id),
        )
        self.conn.commit()

    def start_run(self, session_id, run_type, player_count):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO runs (session_id, run_type, start_time, player_count) VALUES (?, ?, ?, ?)",
            (session_id, run_type, datetime.now().isoformat(), player_count),
        )
        self.conn.commit()
        return cur.lastrowid

    def end_run(self, run_id):
        row = self.conn.execute("SELECT start_time FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return 0.0
        start = datetime.fromisoformat(row["start_time"])
        duration = (datetime.now() - start).total_seconds()
        self.conn.execute(
            "UPDATE runs SET end_time = ?, duration_seconds = ? WHERE id = ?",
            (datetime.now().isoformat(), duration, run_id),
        )
        self.conn.commit()
        return duration

    def add_item(self, run_id, item_name):
        self.conn.execute(
            "INSERT INTO items (run_id, item_name, found_time) VALUES (?, ?, ?)",
            (run_id, item_name, datetime.now().isoformat()),
        )
        self.conn.commit()

    def delete_item_by_id(self, item_id):
        self.conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        self.conn.commit()

    def delete_run(self, run_id):
        self.conn.execute("DELETE FROM items WHERE run_id = ?", (run_id,))
        self.conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        self.conn.commit()

    def get_run_items(self, run_id):
        return self.conn.execute(
            "SELECT id, item_name FROM items WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()

    def get_recent_runs(self, session_id, limit=50):
        return self.conn.execute(
            """
            SELECT
                r.id,
                r.run_type,
                r.player_count,
                r.duration_seconds,
                (
                    SELECT GROUP_CONCAT(i.item_name, ', ')
                    FROM items i
                    WHERE i.run_id = r.id
                ) AS items_found
            FROM runs r
            WHERE r.session_id = ? AND r.end_time IS NOT NULL
            ORDER BY r.id DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()

    def get_session_runs(self, session_id):
        return self.conn.execute(
            """
            SELECT id, session_id, run_type, start_time, end_time, duration_seconds, player_count
            FROM runs
            WHERE session_id = ? AND end_time IS NOT NULL
            ORDER BY id
            """,
            (session_id,),
        ).fetchall()

    def get_session_items(self, session_id):
        return self.conn.execute(
            """
            SELECT i.id, i.item_name, i.run_id, r.run_type, r.player_count
            FROM items i
            JOIN runs r ON i.run_id = r.id
            WHERE r.session_id = ?
            ORDER BY i.id
            """,
            (session_id,),
        ).fetchall()

    def get_session_row(self, session_id):
        return self.conn.execute(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()

    def get_all_sessions(self, character_name=None):
        if character_name:
            return self.conn.execute(
                "SELECT * FROM sessions WHERE character_name = ? ORDER BY id",
                (character_name,),
            ).fetchall()
        return self.conn.execute("SELECT * FROM sessions ORDER BY id").fetchall()

    def get_all_runs_for_sessions(self, session_ids):
        if not session_ids:
            return []
        ph = ",".join("?" * len(session_ids))
        return self.conn.execute(
            f"""
            SELECT id, session_id, run_type, start_time, end_time, duration_seconds, player_count
            FROM runs
            WHERE session_id IN ({ph}) AND end_time IS NOT NULL
            ORDER BY id
            """,
            session_ids,
        ).fetchall()

    def get_all_items_for_sessions(self, session_ids):
        if not session_ids:
            return []
        ph = ",".join("?" * len(session_ids))
        return self.conn.execute(
            f"""
            SELECT i.id, i.item_name, i.run_id, r.run_type, r.player_count, r.session_id
            FROM items i
            JOIN runs r ON i.run_id = r.id
            WHERE r.session_id IN ({ph})
            ORDER BY i.id
            """,
            session_ids,
        ).fetchall()

    def count_completed_runs(self, session_id):
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM runs WHERE session_id = ? AND end_time IS NOT NULL",
            (session_id,),
        ).fetchone()
        return int(row["n"]) if row else 0

    def close(self):
        self.conn.close()


class AutocompleteEntry(tk.Frame):
    def __init__(self, parent, suggestions, on_submit=None, **kw):
        super().__init__(parent, **kw)
        self.suggestions = suggestions
        self.on_submit = on_submit

        self.var = tk.StringVar()
        self.entry = tk.Entry(
            self,
            textvariable=self.var,
            font=("Segoe UI", 11),
            bg="#2a2a3a",
            fg="#e0e0e0",
            insertbackground="#e0e0e0",
            relief="flat",
            bd=4,
        )
        self.entry.pack(fill=tk.X)
        self.entry.bind("<KeyRelease>", self._on_key)
        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<Down>", self._focus_list)
        self.entry.bind("<Escape>", lambda e: self._hide())

        self._popup = None
        self._listbox = None

    def _on_key(self, event):
        if event.keysym in ("Down", "Up", "Return", "Escape"):
            return
        val = self.var.get().strip()
        if not val:
            self._hide()
            return
        matches = [s for s in self.suggestions if val.lower() in s.lower()][:14]
        if matches:
            self._show(matches)
        else:
            self._hide()

    def _show(self, matches):
        self._hide()
        self._popup = tk.Toplevel(self)
        self._popup.wm_overrideredirect(True)
        self._popup.attributes("-topmost", True)
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()
        self._popup.geometry(f"+{x}+{y}")
        self._listbox = tk.Listbox(
            self._popup,
            font=("Segoe UI", 10),
            bg="#1e1e2e",
            fg="#e0e0e0",
            selectbackground="#4a4a6a",
            selectforeground="#ffffff",
            relief="flat",
            bd=1,
            highlightthickness=1,
            highlightcolor="#6a6a9a",
            width=60,
            height=min(len(matches), 14),
        )
        self._listbox.pack()
        for m in matches:
            self._listbox.insert(tk.END, m)
        self._listbox.bind("<ButtonRelease-1>", self._pick)
        self._listbox.bind("<Return>", self._pick)

    def _hide(self):
        if self._popup:
            self._popup.destroy()
            self._popup = None
            self._listbox = None

    def _pick(self, _event=None):
        if self._listbox and self._listbox.curselection():
            self.var.set(self._listbox.get(self._listbox.curselection()[0]))
        self._hide()

    def _focus_list(self, _event=None):
        if self._listbox:
            self._listbox.focus_set()
            self._listbox.selection_set(0)

    def _on_enter(self, _event=None):
        value = self.var.get().strip()
        if value and self.on_submit:
            self.on_submit(value)
            self.clear()

    def clear(self):
        self.var.set("")
        self._hide()

    def focus_input(self):
        self.entry.focus_set()


class StatsPane(tk.Frame):
    def __init__(self, parent, title, bg, fg, gold):
        super().__init__(parent, bg=bg, bd=1, relief="groove")
        self.bg = bg
        self.fg = fg
        self.gold = gold
        self.title = title
        self.group_rows = []

        tk.Label(
            self,
            text=title,
            font=("Segoe UI", 12, "bold"),
            fg=gold,
            bg=bg,
            pady=6,
        ).pack(fill=tk.X)

        self.summary = tk.Text(
            self,
            height=7,
            font=("Consolas", 11),
            bg="#22223a",
            fg="#e0e0e0",
            relief="flat",
            wrap=tk.WORD,
            padx=8,
            pady=6,
        )
        self.summary.pack(fill=tk.X, padx=8, pady=(0, 8))
        self.summary.configure(state=tk.DISABLED)

        selector_row = tk.Frame(self, bg=bg)
        selector_row.pack(fill=tk.X, padx=8, pady=(0, 8))
        tk.Label(
            selector_row,
            text="Group:",
            font=("Segoe UI", 11, "bold"),
            fg=fg,
            bg=bg,
        ).pack(side=tk.LEFT)

        self.group_var = tk.StringVar(value="Overall")
        self.combo = ttk.Combobox(
            selector_row,
            textvariable=self.group_var,
            state="readonly",
            font=("Segoe UI", 11),
        )
        self.combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))
        self.combo.bind("<<ComboboxSelected>>", self._on_group_change)

        self.detail = tk.Text(
            self,
            font=("Consolas", 11),
            bg="#22223a",
            fg="#d0d0f0",
            relief="flat",
            wrap=tk.WORD,
            padx=8,
            pady=8,
        )
        self.detail.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.detail.configure(state=tk.DISABLED)

        self.render_empty("No data yet.")

    def render_empty(self, message):
        self.group_rows = []
        self.combo["values"] = ["Overall"]
        self.group_var.set("Overall")
        self._set_text(self.summary, [message])
        self._set_text(self.detail, ["No detail available."])

    def load_scope(self, scope_data):
        if not scope_data["runs"]:
            self.render_empty("No completed runs yet.")
            return

        overall = scope_data["overall"]
        summary_lines = [
            f"Total Runs: {overall['total_runs']}",
            f"Session Time: {overall['session_time_text']}",
            f"Time in Runs: {overall['run_time_text']}",
            f"Avg Run Time: {overall['avg_run_text']}",
            f"Fastest Run: {overall['fastest_text']}",
            f"Items Found: {overall['item_count']}",
            f"Runs / Hour (incl. downtime): {overall['runs_per_hour_scope']:.1f}",
        ]
        self._set_text(self.summary, summary_lines)

        values = ["Overall"] + [group["label"] for group in scope_data["groups"]]
        self.combo["values"] = values

        current = self.group_var.get()
        if current not in values:
            current = "Overall"
            self.group_var.set(current)

        self.group_rows = scope_data["groups"]
        self._render_group_detail(current)

    def _on_group_change(self, _event=None):
        self._render_group_detail(self.group_var.get())

    def _render_group_detail(self, selection):
        if selection == "Overall":
            lines = ["Grouped by run type + players:"]
            if not self.group_rows:
                lines.append("No grouped data available.")
            else:
                for group in self.group_rows:
                    lines.append(
                        f"- {group['label']}: {group['run_count']} runs, "
                        f"avg {group['avg_run_text']}, "
                        f"{group['item_count']} items, "
                        f"{group['items_per_run']:.2f} items/run"
                    )
                lines.append("")
                lines.append("Select a group above to see item drop rates.")
            self._set_text(self.detail, lines)
            return

        group = next((g for g in self.group_rows if g["label"] == selection), None)
        if not group:
            self._set_text(self.detail, ["No detail available."])
            return

        lines = [
            selection,
            "",
            f"Runs: {group['run_count']}",
            f"Avg Run Time: {group['avg_run_text']}",
            f"Fastest Run: {group['fastest_text']}",
            f"Slowest Run: {group['slowest_text']}",
            f"Time in Runs: {group['run_time_text']}",
            f"Items Found: {group['item_count']}",
            f"Items / Run: {group['items_per_run']:.2f}",
            f"Share of scope runs: {group['run_share_pct']:.1f}%",
            "",
            "Item drop rates:",
        ]
        if group["item_rates"]:
            for item_name, count, pct in group["item_rates"]:
                lines.append(f"- {item_name}: {count} ({pct:.1f}%)")
        else:
            lines.append("- No items recorded for this group.")
        self._set_text(self.detail, lines)

    def _set_text(self, widget, lines):
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", "\n".join(lines))
        widget.configure(state=tk.DISABLED)


class D2RMFTracker:
    BG = "#1a1a2e"
    BG2 = "#22223a"
    FG = "#e0e0e0"
    GOLD = "#ffd700"
    PURPLE = "#8888cc"
    GREEN = "#44ff44"
    ORANGE = "#ffaa00"

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("D2R MF Tracker")
        self.root.configure(bg=self.BG)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.98)
        self.root.overrideredirect(True)
        self.normal_width = 600
        self.normal_height = 860
        self.mini_width = 220
        self.mini_height = 118
        self.min_normal_width = 460
        self.min_mini_width = 180
        self.root.geometry("600x460")
        self.root.resizable(False, False)

        self.config_path = os.path.join(os.path.expanduser("~"), ".d2r_mf_tracker_config.json")
        self.app_config = self._load_config()

        self.is_mini_mode = False

        self.db = None
        self.character_name = ""
        self.session_id = None
        self.session_start_time = None
        self.session_running = False

        self.current_run_id = None
        self.run_start_time = None
        self.run_running = False
        self.run_count = 0
        self.last_completed_run_id = None

        self.show_recent_runs = tk.BooleanVar(value=True)
        self.borderless = tk.BooleanVar(value=True)
        self.overlay_alpha = tk.DoubleVar(value=0.98)

        self._drag_data = {"x": 0, "y": 0}
        self._item_id_map = {}
        self._recent_run_map = {}
        self._hotkey_handles = []

        self.auto_settings = self._load_auto_settings()
        self.auto_enabled = tk.BooleanVar(value=bool(self.auto_settings.get("enabled")))
        self.detector = None
        self._auto_status = "Auto-detect off"
        self._item_index = vision.build_item_index(D2R_ITEMS) if VISION_MODULE else {}
        if VISION_MODULE:
            vision.set_tesseract_path(self.auto_settings.get("tesseract_path"))

        self._build_setup_screen()

    # ------------------------------------------------------------------
    # Auto-detect settings
    # ------------------------------------------------------------------
    def _load_auto_settings(self):
        stored = self.app_config.get("auto_detect")
        settings = dict(DEFAULT_AUTO_SETTINGS)
        if isinstance(stored, dict):
            settings.update(stored)
        return settings

    def _save_auto_settings(self):
        self.auto_settings["enabled"] = bool(self.auto_enabled.get())
        self.app_config["auto_detect"] = self.auto_settings
        self._save_config()

    def _load_config(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def _save_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.app_config, f, indent=2)
        except OSError:
            pass

    def _get_last_db_path(self):
        path = str(self.app_config.get("last_db_path", "")).strip()
        return path

    def _remember_database_path(self, path):
        clean_path = os.path.abspath(path)
        self.app_config["last_db_path"] = clean_path
        self._save_config()

    def _default_new_db_path(self):
        last_path = self._get_last_db_path()
        if last_path:
            return last_path
        return os.path.join(os.getcwd(), "d2r_mf_tracker.db")

    def _set_db_path(self, path):
        if not path:
            return
        clean_path = os.path.abspath(path)
        self.db_var.set(clean_path)
        if hasattr(self, "db_hint_label"):
            exists_text = "existing database" if os.path.exists(clean_path) else "new database will be created"
            self.db_hint_label.config(text=f"Selected: {exists_text}")
        if hasattr(self, "last_db_label"):
            self.last_db_label.config(text=f"Last used: {clean_path}")

    def _select_existing_db(self):
        initial = self._get_last_db_path() or self._default_new_db_path()
        initial_dir = os.path.dirname(initial) if initial else os.getcwd()
        path = filedialog.askopenfilename(
            title="Select Existing Database",
            initialdir=initial_dir,
            filetypes=[("SQLite Database", "*.db *.sqlite *.sqlite3"), ("All Files", "*.*")],
        )
        if path:
            self._set_db_path(path)

    def _create_new_db(self):
        initial = self._default_new_db_path()
        initial_dir = os.path.dirname(initial) if initial else os.getcwd()
        initial_file = os.path.basename(initial) if initial else "d2r_mf_tracker.db"
        path = filedialog.asksaveasfilename(
            title="Create New Database",
            initialdir=initial_dir,
            initialfile=initial_file,
            defaultextension=".db",
            filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")],
        )
        if path:
            self._set_db_path(path)

    def _build_setup_screen(self):
        frame = tk.Frame(self.root, bg=self.BG, padx=24, pady=24)
        frame.pack(fill=tk.BOTH, expand=True)
        self.setup_frame = frame

        tk.Label(
            frame,
            text="⚔  D2R MF Run Tracker  ⚔",
            font=("Segoe UI", 18, "bold"),
            fg=self.GOLD,
            bg=self.BG,
        ).pack(pady=(0, 20))

        tk.Label(frame, text="Character Name:", font=("Segoe UI", 11), fg=self.FG, bg=self.BG).pack(anchor="w")
        self.char_var = tk.StringVar()
        tk.Entry(
            frame,
            textvariable=self.char_var,
            font=("Segoe UI", 11),
            bg="#2a2a3a",
            fg=self.FG,
            insertbackground=self.FG,
            relief="flat",
            bd=5,
        ).pack(fill=tk.X, pady=(2, 16))

        tk.Label(frame, text="Database (SQLite):", font=("Segoe UI", 11), fg=self.FG, bg=self.BG).pack(anchor="w")
        last_db_path = self._get_last_db_path()
        initial_db_path = last_db_path if last_db_path else self._default_new_db_path()
        self.db_var = tk.StringVar(value=initial_db_path)

        selector = tk.Frame(frame, bg=self.BG)
        selector.pack(fill=tk.X, pady=(2, 8))

        tk.Entry(
            selector,
            textvariable=self.db_var,
            font=("Segoe UI", 11),
            bg="#2a2a3a",
            fg=self.FG,
            insertbackground=self.FG,
            relief="flat",
            bd=5,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(
            selector,
            text="Select…",
            command=self._select_existing_db,
            font=("Segoe UI", 10),
            bg="#3a3a5a",
            fg=self.FG,
            activebackground="#4a4a6a",
            relief="flat",
            padx=10,
        ).pack(side=tk.LEFT, padx=(6, 0))

        tk.Button(
            selector,
            text="New…",
            command=self._create_new_db,
            font=("Segoe UI", 10),
            bg="#3a3a5a",
            fg=self.FG,
            activebackground="#4a4a6a",
            relief="flat",
            padx=10,
        ).pack(side=tk.LEFT, padx=(6, 0))

        self.db_hint_label = tk.Label(
            frame,
            text="Select an existing database or create a new one.",
            font=("Segoe UI", 10),
            fg="#889",
            bg=self.BG,
        )
        self.db_hint_label.pack(anchor="w", pady=(0, 4))

        last_text = f"Last used: {last_db_path}" if last_db_path else "Last used: none yet"
        self.last_db_label = tk.Label(
            frame,
            text=last_text,
            font=("Segoe UI", 10),
            fg="#889",
            bg=self.BG,
            wraplength=540,
            justify="left",
        )
        self.last_db_label.pack(anchor="w", pady=(0, 16))

        hk_text = "Alt+1 Run  │  Alt+2 Item  │  Alt+3 Stats"
        if GLOBAL_HOTKEYS:
            hk_text += "  │  global hotkeys on"
        else:
            hk_text += "  │  install 'keyboard' for global hotkeys"
        tk.Label(frame, text=hk_text, font=("Segoe UI", 10), fg="#889", bg=self.BG).pack(anchor="w", pady=(0, 16))

        tk.Button(
            frame,
            text="🎮  Launch Tracker",
            command=self._launch,
            font=("Segoe UI", 13, "bold"),
            bg="#4a0e8f",
            fg="#fff",
            activebackground="#5a1e9f",
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
        ).pack()

        self._set_db_path(initial_db_path)

    def _launch(self):
        name = self.char_var.get().strip()
        path = self.db_var.get().strip()
        if not name:
            messagebox.showwarning("Oops", "Enter a character name.")
            return
        if not path:
            messagebox.showwarning("Oops", "Select an existing database or create a new one.")
            return

        path = os.path.abspath(path)
        if not os.path.exists(path):
            create_new = messagebox.askyesno(
                "Create Database",
                f"No database exists at:\n\n{path}\n\nCreate a new database there?",
            )
            if not create_new:
                return

        self.character_name = name
        try:
            self.db = Database(path)
        except Exception as exc:
            messagebox.showerror("DB Error", str(exc))
            return

        self._remember_database_path(path)
        self.setup_frame.destroy()
        self._build_overlay()

    def _section(self, parent, title):
        lf = tk.LabelFrame(
            parent,
            text=f"  {title}  ",
            font=("Segoe UI", 11, "bold"),
            fg=self.PURPLE,
            bg=self.BG,
            bd=1,
            relief="groove",
            labelanchor="n",
        )
        return lf

    def _build_overlay(self):
        title_bar = tk.Frame(self.root, bg="#12122a", cursor="fleur")
        title_bar.pack(fill=tk.X)
        title_bar.grid_columnconfigure(1, weight=1)
        self.title_bar = title_bar

        self.title_label = tk.Label(
            title_bar,
            text=f"⚔  {self.character_name}",
            font=("Segoe UI", 12, "bold"),
            fg=self.GOLD,
            bg="#12122a",
            padx=8,
            pady=6,
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        self.title_spacer = tk.Frame(title_bar, bg="#12122a")
        self.title_spacer.grid(row=0, column=1, sticky="ew")

        self.btn_frame = tk.Frame(title_bar, bg="#12122a")
        self.btn_frame.grid(row=0, column=2, sticky="e", padx=(4, 0), pady=4)

        self.btn_mode_toggle = tk.Button(
            self.btn_frame,
            text="Compact",
            command=self._toggle_mini_mode,
            font=("Segoe UI", 10),
            bg="#2a2a3a",
            fg=self.FG,
            activebackground="#3a3a5a",
            relief="flat",
            padx=6,
            pady=2,
        )
        self.btn_mode_toggle.pack(side=tk.LEFT, padx=2)

        self.btn_recent_toggle = tk.Button(
            self.btn_frame,
            text="Recent: On",
            command=self._toggle_recent_runs,
            font=("Segoe UI", 10),
            bg="#2a2a3a",
            fg=self.FG,
            activebackground="#3a3a5a",
            relief="flat",
            padx=6,
            pady=2,
        )
        self.btn_recent_toggle.pack(side=tk.LEFT, padx=2)

        self.btn_display = tk.Button(
            self.btn_frame,
            text="Display",
            command=self._show_display_settings,
            font=("Segoe UI", 10),
            bg="#2a2a3a",
            fg=self.FG,
            activebackground="#3a3a5a",
            relief="flat",
            padx=6,
            pady=2,
        )
        self.btn_display.pack(side=tk.LEFT, padx=2)

        self.btn_stats = tk.Button(
            self.btn_frame,
            text="Stats",
            command=self._show_stats,
            font=("Segoe UI", 10),
            bg="#2a2a3a",
            fg=self.FG,
            activebackground="#3a3a5a",
            relief="flat",
            padx=6,
            pady=2,
        )
        self.btn_stats.pack(side=tk.LEFT, padx=2)

        self.close_frame = tk.Frame(title_bar, bg="#12122a")
        self.close_frame.grid(row=0, column=3, sticky="e", padx=(4, 4), pady=4)

        self.btn_close = tk.Button(
            self.close_frame,
            text="✕",
            command=self._on_close,
            font=("Segoe UI", 10),
            bg="#5a1a1a",
            fg=self.FG,
            activebackground="#7a2a2a",
            relief="flat",
            padx=6,
            pady=2,
        )
        self.btn_close.pack()

        for widget in (title_bar, self.title_label, self.title_spacer):
            widget.bind("<Button-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)

        # Scrollable content area for smaller window sizes
        self.content_container = tk.Frame(self.root, bg=self.BG)
        self.content_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6, 0))

        self.content_canvas = tk.Canvas(
            self.content_container,
            bg=self.BG,
            highlightthickness=0,
            bd=0,
        )
        self.content_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.content_scrollbar = tk.Scrollbar(
            self.content_container,
            orient="vertical",
            command=self.content_canvas.yview,
        )
        self.content_canvas.configure(yscrollcommand=self.content_scrollbar.set)

        self.main_frame = tk.Frame(self.content_canvas, bg=self.BG)
        self.canvas_window = self.content_canvas.create_window(
            (0, 0),
            window=self.main_frame,
            anchor="nw",
        )

        self.main_frame.bind("<Configure>", self._on_main_frame_configure)
        self.content_canvas.bind("<Configure>", self._on_canvas_configure)
        self.content_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.content_canvas.bind("<Button-4>", lambda e: self._on_mousewheel_linux(-1))
        self.content_canvas.bind("<Button-5>", lambda e: self._on_mousewheel_linux(1))

        main = self.main_frame
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(3, weight=1)
        main.grid_rowconfigure(4, weight=1)

        self.bottom_bar = tk.Frame(self.root, bg=self.BG)
        self.bottom_bar.pack(fill=tk.X, padx=8, pady=(4, 6))

        self.footer = tk.Label(
            self.bottom_bar,
            text="Alt+1: Start/Stop Run  │  Alt+2: Focus Item Entry  │  Alt+3: Stats",
            font=("Segoe UI", 10),
            fg="#555577",
            bg=self.BG,
        )
        self.footer.pack(side=tk.LEFT)

        self.resize_grip = tk.Label(
            self.bottom_bar,
            text="↔",
            font=("Segoe UI", 11),
            fg="#777799",
            bg=self.BG,
            cursor="sb_h_double_arrow",
            padx=4,
        )
        self.resize_grip.pack(side=tk.RIGHT)
        self.resize_grip.bind("<Button-1>", self._resize_start)
        self.resize_grip.bind("<B1-Motion>", self._resize_move)

        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.style.configure(
            "Tracker.TCombobox",
            fieldbackground="#2a2a3a",
            background="#3a3a5a",
            foreground=self.FG,
            arrowcolor=self.FG,
            font=("Segoe UI", 11),
        )

        self.sec_session = self._section(main, "Session")
        self.sec_session.grid(row=0, column=0, sticky="ew", pady=4)
        self.lbl_session_time = tk.Label(
            self.sec_session,
            text="00:00:00",
            font=("Consolas", 24, "bold"),
            fg=self.GREEN,
            bg=self.BG,
        )
        self.lbl_session_time.pack(pady=4)
        self.btn_session = tk.Button(
            self.sec_session,
            text="▶  Start Session",
            command=self._toggle_session,
            font=("Segoe UI", 11, "bold"),
            bg="#1a6b1a",
            fg="#fff",
            activebackground="#2a7b2a",
            relief="flat",
            pady=4,
        )
        self.btn_session.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.sec_run_type = self._section(main, "Run Type")
        self.sec_run_type.grid(row=1, column=0, sticky="ew", pady=4)
        row = tk.Frame(self.sec_run_type, bg=self.BG)
        row.pack(fill=tk.X, padx=8, pady=8)
        row.grid_columnconfigure(0, weight=1)

        self.run_type_var = tk.StringVar(value=RUN_TYPES[0])
        self.combo_run = ttk.Combobox(
            row,
            textvariable=self.run_type_var,
            values=RUN_TYPES,
            state="readonly",
            style="Tracker.TCombobox",
        )
        self.combo_run.grid(row=0, column=0, sticky="ew")

        self.player_count_var = tk.StringVar(value="P1")
        self.combo_players = ttk.Combobox(
            row,
            textvariable=self.player_count_var,
            values=PLAYER_COUNTS,
            state="readonly",
            style="Tracker.TCombobox",
            width=6,
        )
        self.combo_players.grid(row=0, column=1, sticky="e", padx=(8, 0))

        self.sec_run = self._section(main, "Current Run")
        self.sec_run.grid(row=2, column=0, sticky="ew", pady=4)
        self.lbl_run_time = tk.Label(
            self.sec_run,
            text="00:00.0",
            font=("Consolas", 20, "bold"),
            fg=self.ORANGE,
            bg=self.BG,
        )
        self.lbl_run_time.pack(pady=4)
        self.lbl_run_count = tk.Label(
            self.sec_run,
            text="Runs this session: 0",
            font=("Segoe UI", 11),
            fg="#8888aa",
            bg=self.BG,
        )
        self.lbl_run_count.pack()
        self.lbl_run_type_active = tk.Label(
            self.sec_run,
            text="",
            font=("Segoe UI", 11, "italic"),
            fg=self.PURPLE,
            bg=self.BG,
        )
        self.lbl_run_type_active.pack()
        self.btn_run = tk.Button(
            self.sec_run,
            text="⏱  Start Run   [Alt+1]",
            command=self._toggle_run,
            font=("Segoe UI", 11, "bold"),
            bg="#0e4a8f",
            fg="#fff",
            activebackground="#1e5a9f",
            relief="flat",
            pady=4,
            state=tk.DISABLED,
        )
        self.btn_run.pack(fill=tk.X, padx=8, pady=(6, 8))

        self.sec_items = self._section(main, "Items Found (last / current run)")
        self.sec_items.grid(row=3, column=0, sticky="nsew", pady=4)
        self.sec_items.grid_rowconfigure(2, weight=1)
        self.sec_items.grid_columnconfigure(0, weight=1)

        self.item_entry = AutocompleteEntry(self.sec_items, D2R_ITEMS, on_submit=self._add_item, bg=self.BG)
        self.item_entry.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 2))
        self.lbl_item_help = tk.Label(
            self.sec_items,
            text="Type item name + Enter  │  Alt+2 focus entry  │  Alt+4 capture item under cursor",
            font=("Segoe UI", 10),
            fg="#666688",
            bg=self.BG,
        )
        self.lbl_item_help.grid(row=1, column=0, sticky="w", padx=8, pady=(0, 4))

        item_list_frame = tk.Frame(self.sec_items, bg=self.BG)
        item_list_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 4))
        item_list_frame.grid_rowconfigure(0, weight=1)
        item_list_frame.grid_columnconfigure(0, weight=1)

        self.items_listbox = tk.Listbox(
            item_list_frame,
            font=("Segoe UI", 11),
            bg=self.BG2,
            fg=self.FG,
            selectbackground="#4a4a6a",
            relief="flat",
            bd=1,
            highlightthickness=1,
            highlightcolor="#3a3a5a",
        )
        self.items_listbox.grid(row=0, column=0, sticky="nsew")
        item_scroll = tk.Scrollbar(item_list_frame, command=self.items_listbox.yview)
        item_scroll.grid(row=0, column=1, sticky="ns")
        self.items_listbox.config(yscrollcommand=item_scroll.set)

        btns = tk.Frame(self.sec_items, bg=self.BG)
        btns.grid(row=3, column=0, pady=(0, 8))
        tk.Button(
            btns,
            text="🗑  Remove Selected Item",
            command=self._remove_item,
            font=("Segoe UI", 10),
            bg="#5a1a1a",
            fg=self.FG,
            activebackground="#7a2a2a",
            relief="flat",
            padx=8,
            pady=2,
        ).pack()

        self.sec_recent = self._section(main, "Recent Runs")
        self.sec_recent.grid(row=4, column=0, sticky="nsew", pady=4)
        self.sec_recent.grid_rowconfigure(0, weight=1)
        self.sec_recent.grid_columnconfigure(0, weight=1)

        recent_frame = tk.Frame(self.sec_recent, bg=self.BG)
        recent_frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        recent_frame.grid_rowconfigure(0, weight=1)
        recent_frame.grid_columnconfigure(0, weight=1)

        self.recent_listbox = tk.Listbox(
            recent_frame,
            font=("Consolas", 10),
            bg=self.BG2,
            fg="#aaaacc",
            selectbackground="#4a4a6a",
            relief="flat",
            bd=1,
            highlightthickness=1,
            highlightcolor="#3a3a5a",
        )
        self.recent_listbox.grid(row=0, column=0, sticky="nsew")
        recent_scroll = tk.Scrollbar(recent_frame, command=self.recent_listbox.yview)
        recent_scroll.grid(row=0, column=1, sticky="ns")
        self.recent_listbox.config(yscrollcommand=recent_scroll.set)

        tk.Button(
            self.sec_recent,
            text="🗑  Remove Selected Run",
            command=self._remove_selected_recent_run,
            font=("Segoe UI", 10),
            bg="#5a1a1a",
            fg=self.FG,
            activebackground="#7a2a2a",
            relief="flat",
            padx=8,
            pady=2,
        ).grid(row=1, column=0, pady=(0, 8))

        self._build_auto_detect_bar(main)
        self._build_mini_hud()

        self.root.bind_all("<Alt-Key-1>", lambda e: self._toggle_run())
        self.root.bind_all("<Alt-Key-2>", lambda e: self.item_entry.focus_input())
        self.root.bind_all("<Alt-Key-3>", lambda e: self._show_stats())
        self.root.bind_all("<Alt-Key-4>", lambda e: self._capture_item_at_cursor())

        if GLOBAL_HOTKEYS:
            self._hotkey_handles.append(kb.add_hotkey("alt+1", lambda: self.root.after(0, self._toggle_run)))
            self._hotkey_handles.append(kb.add_hotkey("alt+2", lambda: self.root.after(0, self.item_entry.focus_input)))
            self._hotkey_handles.append(kb.add_hotkey("alt+3", lambda: self.root.after(0, self._show_stats)))
            self._hotkey_handles.append(kb.add_hotkey("alt+4", lambda: self.root.after(0, self._capture_item_at_cursor)))

        if self.auto_enabled.get():
            # Give the overlay a moment to finish laying out before the watcher
            # thread starts pushing status updates into it.
            self.root.after(500, self._toggle_auto_detect_on_launch)

        self._configure_overlay_window()
        self._apply_recent_runs_visibility()
        self._sync_session_controls()
        self._sync_run_controls()
        self.root.after(50, self._update_content_scrollbar)
        self._tick()

    def _build_auto_detect_bar(self, parent):
        """Compact auto-detect toggle, status line, and settings entry point."""
        bar = tk.Frame(parent, bg="#12122a", bd=1, relief="flat")
        bar.grid(row=5, column=0, sticky="ew", pady=(4, 2))
        bar.grid_columnconfigure(1, weight=1)

        tk.Checkbutton(
            bar,
            text="Auto-detect runs",
            variable=self.auto_enabled,
            command=self._toggle_auto_detect,
            bg="#12122a",
            fg=self.FG,
            activebackground="#12122a",
            activeforeground=self.FG,
            selectcolor="#2a2a3a",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=(8, 4), pady=4)

        tk.Button(
            bar,
            text="⚙  Calibrate…",
            command=self._show_auto_settings,
            font=("Segoe UI", 9),
            bg="#2a2a4a",
            fg=self.FG,
            relief="flat",
            padx=8,
        ).grid(row=0, column=2, sticky="e", padx=(4, 8), pady=4)

        self.lbl_auto_status = tk.Label(
            bar,
            text=f"👁  {self._auto_status}",
            font=("Segoe UI", 9),
            fg=self.PURPLE,
            bg="#12122a",
            anchor="w",
        )
        self.lbl_auto_status.grid(row=1, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 5))

    def _toggle_auto_detect_on_launch(self):
        """Restore the saved auto-detect state once the overlay is up."""
        if not self._start_detector():
            self.auto_enabled.set(False)

    def _build_mini_hud(self):
        self.mini_hud = tk.Frame(self.root, bg="#101626", bd=1, relief="solid")

        mini_top = tk.Frame(self.mini_hud, bg="#0b1220", cursor="fleur")
        mini_top.pack(fill=tk.X, padx=1, pady=(1, 0))

        self.mini_title = tk.Label(
            mini_top,
            text="MF",
            font=("Segoe UI", 8, "bold"),
            fg=self.GOLD,
            bg="#0b1220",
            padx=4,
            pady=2,
        )
        self.mini_title.pack(side=tk.LEFT)

        self.btn_mini_close = tk.Button(
            mini_top,
            text="✕",
            command=self._on_close,
            font=("Segoe UI", 7, "bold"),
            bg="#5a1a1a",
            fg=self.FG,
            activebackground="#7a2a2a",
            relief="flat",
            padx=4,
            pady=1,
        )
        self.btn_mini_close.pack(side=tk.RIGHT, padx=(2, 2), pady=2)

        self.btn_mini_expand = tk.Button(
            mini_top,
            text="Open",
            command=self._toggle_mini_mode,
            font=("Segoe UI", 7, "bold"),
            bg="#2a2a3a",
            fg=self.FG,
            activebackground="#3a3a5a",
            relief="flat",
            padx=4,
            pady=1,
        )
        self.btn_mini_expand.pack(side=tk.RIGHT, padx=(0, 2), pady=2)

        for widget in (self.mini_hud, mini_top, self.mini_title):
            widget.bind("<Button-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)

        timer_frame = tk.Frame(self.mini_hud, bg="#101626")
        timer_frame.pack(fill=tk.X, padx=6, pady=(4, 2))
        timer_frame.grid_columnconfigure(0, weight=1)
        timer_frame.grid_columnconfigure(1, weight=1)

        session_box = tk.Frame(timer_frame, bg="#101626")
        session_box.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        tk.Label(
            session_box,
            text="SESSION",
            font=("Segoe UI", 6, "bold"),
            fg="#8fa3bf",
            bg="#101626",
        ).pack(anchor="w")
        self.lbl_mini_session_time = tk.Label(
            session_box,
            text="00:00:00",
            font=("Consolas", 10, "bold"),
            fg=self.GREEN,
            bg="#101626",
        )
        self.lbl_mini_session_time.pack(anchor="w")

        run_box = tk.Frame(timer_frame, bg="#101626")
        run_box.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        tk.Label(
            run_box,
            text="RUN",
            font=("Segoe UI", 6, "bold"),
            fg="#8fa3bf",
            bg="#101626",
        ).pack(anchor="w")
        self.lbl_mini_run_time = tk.Label(
            run_box,
            text="00:00.0",
            font=("Consolas", 10, "bold"),
            fg=self.ORANGE,
            bg="#101626",
        )
        self.lbl_mini_run_time.pack(anchor="w")

        mini_buttons = tk.Frame(self.mini_hud, bg="#101626")
        mini_buttons.pack(fill=tk.X, padx=6, pady=(2, 6))
        mini_buttons.grid_columnconfigure(0, weight=1)
        mini_buttons.grid_columnconfigure(1, weight=1)

        self.btn_mini_session = tk.Button(
            mini_buttons,
            text="Start S",
            command=self._toggle_session,
            font=("Segoe UI", 8, "bold"),
            bg="#1a6b1a",
            fg="#ffffff",
            activebackground="#2a7b2a",
            relief="flat",
            padx=4,
            pady=3,
        )
        self.btn_mini_session.grid(row=0, column=0, sticky="ew", padx=(0, 3))

        self.btn_mini_run = tk.Button(
            mini_buttons,
            text="Run",
            command=self._toggle_run,
            font=("Segoe UI", 8, "bold"),
            bg="#0e4a8f",
            fg="#ffffff",
            activebackground="#1e5a9f",
            relief="flat",
            padx=4,
            pady=3,
            state=tk.DISABLED,
        )
        self.btn_mini_run.grid(row=0, column=1, sticky="ew", padx=(3, 0))

    def _show_normal_layout(self):
        if hasattr(self, "mini_hud"):
            self.mini_hud.pack_forget()
        self.title_bar.pack_forget()
        self.content_container.pack_forget()
        self.bottom_bar.pack_forget()
        self.title_bar.pack(fill=tk.X)
        self.content_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6, 0))
        self.bottom_bar.pack(fill=tk.X, padx=8, pady=(4, 6))

    def _show_mini_layout(self):
        self.title_bar.pack_forget()
        self.content_container.pack_forget()
        self.bottom_bar.pack_forget()
        self.mini_hud.pack_forget()
        self.mini_hud.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    def _sync_session_controls(self):
        if self.session_running:
            self.btn_session.config(text="⏹  End Session", bg="#8b0000")
            self.btn_run.config(state=tk.NORMAL)
            self.btn_mini_session.config(text="End S", bg="#8b0000")
            self.btn_mini_run.config(state=tk.NORMAL)
        else:
            self.btn_session.config(text="▶  Start Session", bg="#1a6b1a")
            self.btn_run.config(state=tk.DISABLED)
            self.btn_mini_session.config(text="Start S", bg="#1a6b1a")
            self.btn_mini_run.config(state=tk.DISABLED)

    def _sync_run_controls(self):
        if self.run_running:
            self.btn_run.config(text="⏹  Stop Run   [Alt+1]", bg="#8b0000")
            self.btn_mini_run.config(text="Stop", bg="#8b0000")
        else:
            self.btn_run.config(text="⏱  Start Run   [Alt+1]", bg="#0e4a8f")
            self.btn_mini_run.config(text="Run", bg="#0e4a8f")

    def _on_main_frame_configure(self, _event=None):
        if hasattr(self, "content_canvas"):
            self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))
            self._update_content_scrollbar()

    def _on_canvas_configure(self, event):
        if hasattr(self, "canvas_window"):
            self.content_canvas.itemconfigure(self.canvas_window, width=event.width)
            self._update_content_scrollbar()

    def _update_content_scrollbar(self):
        if not hasattr(self, "content_canvas") or not hasattr(self, "main_frame"):
            return
        self.root.update_idletasks()
        needs_scroll = self.main_frame.winfo_reqheight() > self.content_canvas.winfo_height() + 2
        if needs_scroll:
            if not self.content_scrollbar.winfo_ismapped():
                self.content_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        else:
            if self.content_scrollbar.winfo_ismapped():
                self.content_scrollbar.pack_forget()
            self.content_canvas.yview_moveto(0)

    def _on_mousewheel(self, event):
        if not hasattr(self, "content_canvas"):
            return
        if self.content_scrollbar.winfo_ismapped():
            self.content_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_linux(self, direction):
        if not hasattr(self, "content_canvas"):
            return
        if self.content_scrollbar.winfo_ismapped():
            self.content_canvas.yview_scroll(direction, "units")

    def _resize_start(self, event):
        self._resize_data = {
            "x": event.x_root,
            "w": self.root.winfo_width(),
        }

    def _resize_move(self, event):
        if not hasattr(self, "_resize_data"):
            return
        dx = event.x_root - self._resize_data["x"]
        min_width = self.min_mini_width if self.is_mini_mode else self.min_normal_width
        screen_width = getattr(self, "screen_width", self.root.winfo_screenwidth())
        new_w = max(min_width, min(self._resize_data["w"] + dx, screen_width))
        self._set_window_size(
            width=new_w,
            min_width=min_width,
            keep_top=not self.is_mini_mode,
        )
        if not self.is_mini_mode:
            self.normal_width = new_w
        self.root.after(10, self._update_content_scrollbar)

    def _show_display_settings(self):
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=self.BG)
        x = self.root.winfo_x() + 40
        y = self.root.winfo_y() + 60
        win.geometry(f"320x180+{x}+{y}")

        top = tk.Frame(win, bg="#12122a")
        top.pack(fill=tk.X)
        tk.Label(top, text="Display Settings", font=("Segoe UI", 11, "bold"), fg=self.GOLD, bg="#12122a", padx=8, pady=6).pack(side=tk.LEFT)
        tk.Button(top, text="✕", command=win.destroy, font=("Segoe UI", 10), bg="#5a1a1a", fg=self.FG, relief="flat").pack(side=tk.RIGHT, padx=6, pady=4)
        top.bind("<Button-1>", lambda e: self._drag_child_start(e, win))
        top.bind("<B1-Motion>", lambda e: self._drag_child_move(e, win))

        body = tk.Frame(win, bg=self.BG, padx=12, pady=12)
        body.pack(fill=tk.BOTH, expand=True)

        tk.Label(body, text="Opacity", font=("Segoe UI", 11, "bold"), fg=self.FG, bg=self.BG).pack(anchor="w")
        tk.Scale(
            body,
            from_=0.45,
            to=1.00,
            resolution=0.01,
            orient="horizontal",
            variable=self.overlay_alpha,
            command=self._set_window_alpha,
            bg=self.BG,
            fg=self.FG,
            highlightthickness=0,
            troughcolor="#2a2a3a",
        ).pack(fill=tk.X)

        tk.Checkbutton(
            body,
            text="Show Recent Runs",
            variable=self.show_recent_runs,
            command=self._apply_recent_runs_visibility,
            bg=self.BG,
            fg=self.FG,
            activebackground=self.BG,
            activeforeground=self.FG,
            selectcolor="#2a2a3a",
            font=("Segoe UI", 11),
        ).pack(anchor="w", pady=(8, 0))

        tk.Checkbutton(
            body,
            text="Borderless Main Window",
            variable=self.borderless,
            command=self._apply_borderless_mode,
            bg=self.BG,
            fg=self.FG,
            activebackground=self.BG,
            activeforeground=self.FG,
            selectcolor="#2a2a3a",
            font=("Segoe UI", 11),
        ).pack(anchor="w", pady=(4, 0))

    # ------------------------------------------------------------------
    # Auto-detect: calibration window
    # ------------------------------------------------------------------
    def _pick_region(self, title, on_done, on_cancel=None):
        """Full-screen drag-a-box selector. Returns screen coordinates."""
        picker = tk.Toplevel(self.root)
        picker.attributes("-fullscreen", True)
        picker.attributes("-topmost", True)
        picker.attributes("-alpha", 0.30)
        picker.configure(bg="#000000", cursor="crosshair")

        canvas = tk.Canvas(picker, bg="#000000", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.create_text(
            picker.winfo_screenwidth() // 2,
            40,
            text=f"{title}  -  drag a box, or press Esc to cancel",
            fill="#ffd700",
            font=("Segoe UI", 16, "bold"),
        )

        state = {"x": 0, "y": 0, "rect": None, "done": False}

        def finish(box):
            if state["done"]:
                return
            state["done"] = True
            picker.destroy()
            if box:
                on_done(box)
            elif on_cancel:
                on_cancel()

        def on_press(event):
            state["x"], state["y"] = event.x, event.y
            if state["rect"]:
                canvas.delete(state["rect"])
            state["rect"] = canvas.create_rectangle(
                event.x, event.y, event.x, event.y, outline="#ffd700", width=2
            )

        def on_drag(event):
            if state["rect"]:
                canvas.coords(state["rect"], state["x"], state["y"], event.x, event.y)

        def on_release(event):
            left, top = min(state["x"], event.x), min(state["y"], event.y)
            width, height = abs(event.x - state["x"]), abs(event.y - state["y"])
            if width > 4 and height > 4:
                finish({"left": left, "top": top, "width": width, "height": height})
            else:
                finish(None)

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        picker.bind("<Escape>", lambda e: finish(None))
        picker.protocol("WM_DELETE_WINDOW", lambda: finish(None))
        picker.focus_force()

    def _show_auto_settings(self):
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=self.BG)
        x = self.root.winfo_x() + 40
        y = self.root.winfo_y() + 60
        win.geometry(f"430x560+{x}+{y}")

        top = tk.Frame(win, bg="#12122a")
        top.pack(fill=tk.X)
        tk.Label(
            top, text="Auto-Detect Settings", font=("Segoe UI", 11, "bold"),
            fg=self.GOLD, bg="#12122a", padx=8, pady=6,
        ).pack(side=tk.LEFT)
        tk.Button(
            top, text="✕", command=win.destroy, font=("Segoe UI", 10),
            bg="#5a1a1a", fg=self.FG, relief="flat",
        ).pack(side=tk.RIGHT, padx=6, pady=4)
        top.bind("<Button-1>", lambda e: self._drag_child_start(e, win))
        top.bind("<B1-Motion>", lambda e: self._drag_child_move(e, win))

        body = tk.Frame(win, bg=self.BG, padx=12, pady=10)
        body.pack(fill=tk.BOTH, expand=True)

        # -- dependency / tesseract status --------------------------------
        if not VISION_MODULE:
            dep_text = "Screen-reading modules not found"
        elif vision.MISSING_DEPS:
            dep_text = "Missing: " + ", ".join(vision.MISSING_DEPS)
        elif not vision.tesseract_available():
            dep_text = "Tesseract binary not found"
        else:
            dep_text = "All dependencies OK"
        dep_row = tk.Frame(body, bg=self.BG)
        dep_row.pack(fill=tk.X, pady=(0, 8))
        lbl_dep = tk.Label(
            dep_row, text=dep_text, font=("Segoe UI", 10),
            fg=self.GREEN if dep_text.endswith("OK") else self.ORANGE, bg=self.BG,
        )
        lbl_dep.pack(side=tk.LEFT)

        def locate_tesseract():
            path = filedialog.askopenfilename(
                title="Locate tesseract.exe",
                filetypes=[("Tesseract", "tesseract.exe"), ("All Files", "*.*")],
            )
            if not path:
                return
            self.auto_settings["tesseract_path"] = path
            self._save_auto_settings()
            vision.set_tesseract_path(path)
            if vision.tesseract_available():
                lbl_dep.config(text="All dependencies OK", fg=self.GREEN)
            else:
                lbl_dep.config(text="That file did not work as Tesseract", fg=self.ORANGE)

        if VISION_MODULE and not vision.MISSING_DEPS and not vision.tesseract_available():
            tk.Button(
                dep_row, text="Locate…", command=locate_tesseract, font=("Segoe UI", 9),
                bg="#2a2a4a", fg=self.FG, relief="flat", padx=8,
            ).pack(side=tk.RIGHT)

        # -- region calibration -------------------------------------------
        region_labels = {}

        def region_text(key):
            box = vision.normalize_region(self.auto_settings.get(key)) if VISION_MODULE else None
            if not box:
                return "not set"
            return f"{box['width']}x{box['height']} at {box['left']},{box['top']}"

        def make_region_row(parent, key, label, hint):
            row = tk.Frame(parent, bg=self.BG)
            row.pack(fill=tk.X, pady=(6, 0))
            tk.Label(
                row, text=label, font=("Segoe UI", 11, "bold"), fg=self.FG, bg=self.BG
            ).pack(anchor="w")
            tk.Label(
                row, text=hint, font=("Segoe UI", 9), fg="#666688", bg=self.BG,
                wraplength=390, justify="left",
            ).pack(anchor="w")
            sub = tk.Frame(row, bg=self.BG)
            sub.pack(fill=tk.X, pady=(2, 0))
            value = tk.Label(
                sub, text=region_text(key), font=("Segoe UI", 10), fg=self.PURPLE, bg=self.BG
            )
            value.pack(side=tk.LEFT)
            region_labels[key] = value

            def do_pick():
                # Hide our own windows so they cannot be picked by mistake.
                win.withdraw()
                self.root.withdraw()

                def restore():
                    self.root.deiconify()
                    win.deiconify()

                def done(box):
                    self.auto_settings[key] = box
                    self._save_auto_settings()
                    if self.detector:
                        self.detector.update_settings(self.auto_settings)
                    restore()
                    value.config(text=region_text(key))

                self.root.after(250, lambda: self._pick_region(label, done, restore))

            tk.Button(
                sub, text="Set…", command=do_pick, font=("Segoe UI", 9),
                bg="#2a2a4a", fg=self.FG, relief="flat", padx=8,
            ).pack(side=tk.RIGHT)

        make_region_row(
            body, "loading_region", "Loading-screen probe",
            "A small box in an area that is bright in game and black during a "
            "loading screen. The middle of the screen works well.",
        )
        make_region_row(
            body, "area_region", "Automap area name",
            "The area name the automap prints at the top of the screen. Leave "
            "unset to time runs purely off loading screens.",
        )

        # -- difficulty ----------------------------------------------------
        tk.Label(
            body, text="Difficulty", font=("Segoe UI", 11, "bold"), fg=self.FG, bg=self.BG
        ).pack(anchor="w", pady=(12, 0))
        tk.Label(
            body, text="The area name does not include difficulty, so pick it here.",
            font=("Segoe UI", 9), fg="#666688", bg=self.BG,
        ).pack(anchor="w")
        diff_var = tk.StringVar(value=self.auto_settings.get("difficulty", "Hell"))

        def on_diff(*_):
            self.auto_settings["difficulty"] = diff_var.get()
            self._save_auto_settings()
            if self.detector:
                self.detector.update_settings(self.auto_settings)

        diff_var.trace_add("write", on_diff)
        ttk.Combobox(
            body, textvariable=diff_var, values=DIFFICULTIES, state="readonly", width=12
        ).pack(anchor="w", pady=(2, 0))

        # -- tuning knobs --------------------------------------------------
        def make_scale(label, key, lo, hi, resolution, hint=""):
            tk.Label(
                body, text=label, font=("Segoe UI", 11, "bold"), fg=self.FG, bg=self.BG
            ).pack(anchor="w", pady=(10, 0))
            if hint:
                tk.Label(
                    body, text=hint, font=("Segoe UI", 9), fg="#666688", bg=self.BG,
                    wraplength=390, justify="left",
                ).pack(anchor="w")
            var = tk.DoubleVar(value=float(self.auto_settings.get(key, lo)))

            def on_change(_value=None):
                self.auto_settings[key] = var.get()
                self._save_auto_settings()
                if self.detector:
                    self.detector.update_settings(self.auto_settings)

            tk.Scale(
                body, from_=lo, to=hi, resolution=resolution, orient="horizontal",
                variable=var, command=on_change, bg=self.BG, fg=self.FG,
                highlightthickness=0, troughcolor="#2a2a3a",
            ).pack(fill=tk.X)

        make_scale(
            "Loading-screen darkness", "dark_threshold", 5, 80, 1,
            "Raise this if loading screens are missed, lower it if dark areas "
            "false-trigger a run.",
        )
        make_scale(
            "Tooltip capture height", "tooltip_height", 60, 400, 10,
            "How tall a box to grab above the cursor when capturing an item.",
        )
        make_scale(
            "Tooltip capture width", "tooltip_width", 150, 900, 10,
        )

        # -- toggles -------------------------------------------------------
        def make_check(label, key):
            var = tk.BooleanVar(value=bool(self.auto_settings.get(key)))

            def on_toggle():
                self.auto_settings[key] = bool(var.get())
                self._save_auto_settings()
                if self.detector:
                    self.detector.update_settings(self.auto_settings)

            tk.Checkbutton(
                body, text=label, variable=var, command=on_toggle, bg=self.BG, fg=self.FG,
                activebackground=self.BG, activeforeground=self.FG, selectcolor="#2a2a3a",
                font=("Segoe UI", 10),
            ).pack(anchor="w", pady=(6, 0))

        make_check("Stop the run when entering town", "stop_in_town")
        make_check("Fall back to loading screens if no area is read", "fallback_without_area")

        # -- test button ---------------------------------------------------
        result = tk.Label(
            body, text="", font=("Segoe UI", 10), fg=self.PURPLE, bg=self.BG,
            wraplength=390, justify="left",
        )

        def test_area():
            if not VISION_MODULE or not vision.VISION_AVAILABLE:
                result.config(text="Screen-reading modules unavailable")
                return
            frame = vision.grab(self.auto_settings.get("area_region"))
            if frame is None:
                result.config(text="Set the area-name region first")
                return
            masked = vision.mask_colors(
                frame, [vision.AREA_NAME_COLOR],
                tolerance=int(self.auto_settings.get("area_tolerance", 90)),
            )
            text = vision.ocr(masked, single_line=True)
            area, suffix = vision.match_area(text)
            if area:
                result.config(text=f"Read '{text}' → {area.title()} → {suffix or 'not a run area'}")
            else:
                result.config(text=f"Read '{text}' → no area matched")

        tk.Button(
            body, text="🔍  Test area-name OCR", command=test_area, font=("Segoe UI", 10),
            bg="#2a2a4a", fg=self.FG, relief="flat", padx=8, pady=3,
        ).pack(anchor="w", pady=(12, 4))
        result.pack(anchor="w")

    def _set_window_alpha(self, _value=None):
        self.root.attributes("-alpha", max(0.45, min(1.0, self.overlay_alpha.get())))

    def _apply_borderless_mode(self):
        geom = self.root.geometry()
        self.root.overrideredirect(bool(self.borderless.get()))
        self.root.geometry(geom)
        self.root.lift()
        self.root.attributes("-topmost", True)

    def _drag_start(self, event):
        self._drag_data["x"] = event.x_root - self.root.winfo_x()
        self._drag_data["y"] = event.y_root - self.root.winfo_y()

    def _drag_move(self, event):
        x = event.x_root - self._drag_data["x"]
        y = event.y_root - self._drag_data["y"]
        self.root.geometry(f"+{x}+{y}")

    def _drag_child_start(self, event, win):
        win._drag_x = event.x_root - win.winfo_x()
        win._drag_y = event.y_root - win.winfo_y()

    def _drag_child_move(self, event, win):
        x = event.x_root - getattr(win, "_drag_x", 0)
        y = event.y_root - getattr(win, "_drag_y", 0)
        win.geometry(f"+{x}+{y}")

    def _toggle_recent_runs(self):
        self.show_recent_runs.set(not self.show_recent_runs.get())
        self._apply_recent_runs_visibility()

    def _apply_recent_runs_visibility(self):
        if self.show_recent_runs.get():
            self.sec_recent.grid()
            self.btn_recent_toggle.config(text="Recent: On")
        else:
            self.sec_recent.grid_remove()
            self.btn_recent_toggle.config(text="Recent: Off")
        self.root.after(10, self._update_content_scrollbar)


    def _configure_overlay_window(self):
        self.root.update_idletasks()
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()

        self.normal_height = self.screen_height
        self.normal_width = min(max(self.normal_width, self.min_normal_width), self.screen_width)
        self.mini_width = min(max(self.mini_width, self.min_mini_width), min(240, self.screen_width))
        self.mini_height = min(max(self.mini_height, 104), min(128, self.screen_height))

        self.root.geometry(f"{self.normal_width}x{self.normal_height}+0+0")
        self.root.minsize(self.min_normal_width, self.normal_height)
        self.root.maxsize(self.screen_width, self.normal_height)
        self.root.resizable(True, False)

    def _set_window_size(self, *, width=None, height=None, min_width=None, keep_top=True):
        self.root.update_idletasks()
        current_width = self.root.winfo_width()
        current_height = self.root.winfo_height()
        target_width = current_width if width is None else width
        target_height = current_height if height is None else height
        minimum_width = self.min_normal_width if min_width is None else min_width

        screen_width = getattr(self, "screen_width", self.root.winfo_screenwidth())
        target_width = max(minimum_width, min(target_width, screen_width))
        x = 0
        y = 0

        self.root.minsize(minimum_width, target_height)
        self.root.maxsize(screen_width, target_height)
        self.root.resizable(True, False)
        self.root.geometry(f"{target_width}x{target_height}+{x}+{y}")

    def _refresh_control_visibility(self):
        normal_controls = (
            self.btn_recent_toggle,
            self.btn_display,
            self.btn_stats,
        )
        if self.is_mini_mode:
            for widget in normal_controls:
                widget.pack_forget()
        else:
            for widget in normal_controls:
                if not widget.winfo_manager():
                    widget.pack(side=tk.LEFT, padx=2)


    def _set_root_size(self, width, height):
        self.root.update_idletasks()
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _toggle_mini_mode(self):
        if self.is_mini_mode:
            self._apply_normal_mode()
        else:
            self._apply_mini_mode()

    def _apply_mini_mode(self):
        self.normal_width = max(self.min_normal_width, self.root.winfo_width())
        self.is_mini_mode = True
        self.btn_mode_toggle.config(text="Compact")
        self._show_mini_layout()
        self.root.geometry(f"{self.mini_width}x{self.mini_height}+0+0")
        self.root.minsize(self.mini_width, self.mini_height)
        self.root.maxsize(self.mini_width, self.mini_height)
        self.root.resizable(False, False)

    def _apply_normal_mode(self):
        self.is_mini_mode = False
        self.btn_mode_toggle.config(text="Compact")
        self._show_normal_layout()
        self._refresh_control_visibility()
        self._apply_recent_runs_visibility()
        self._set_window_size(width=self.normal_width, height=self.normal_height, min_width=self.min_normal_width, keep_top=True)
        self.root.after(10, self._update_content_scrollbar)

    # ------------------------------------------------------------------
    # Auto-detect: lifecycle and callbacks
    # ------------------------------------------------------------------
    def _toggle_auto_detect(self):
        if self.auto_enabled.get():
            if not self._start_detector():
                self.auto_enabled.set(False)
        else:
            self._stop_detector()
        self._save_auto_settings()

    def _start_detector(self):
        if not VISION_MODULE:
            self._set_auto_status("Auto-detect needs the screen-reading modules")
            return False
        if not vision.VISION_AVAILABLE:
            self._set_auto_status("Missing: " + ", ".join(vision.MISSING_DEPS))
            return False
        if not vision.tesseract_available():
            self._set_auto_status("Tesseract not found - set its path in Auto-Detect settings")
            return False

        if self.detector is None:
            self.detector = d2r_autodetect.RunDetector(
                self.auto_settings,
                RUN_TYPES,
                on_run_start=self._auto_run_start,
                on_run_end=self._auto_run_end,
                on_status=self._auto_status_cb,
            )
        else:
            self.detector.update_settings(self.auto_settings)
            if self.detector.running:
                return True
        return self.detector.start()

    def _stop_detector(self):
        if self.detector is not None:
            self.detector.stop()
        self._set_auto_status("Auto-detect off")

    # These three are called from the detector thread, so they only schedule
    # work onto the Tk main loop - same pattern as the global hotkeys.
    def _auto_run_start(self, run_type):
        self.root.after(0, lambda: self._apply_auto_run_start(run_type))

    def _auto_run_end(self):
        self.root.after(0, self._apply_auto_run_end)

    def _auto_status_cb(self, message):
        self.root.after(0, lambda: self._set_auto_status(message))

    def _apply_auto_run_start(self, run_type):
        if not self.session_running or self.run_running:
            return
        if run_type and run_type in RUN_TYPES:
            self.run_type_var.set(run_type)
        self._toggle_run(from_detector=True)

    def _apply_auto_run_end(self):
        if self.run_running:
            self._toggle_run(from_detector=True)

    def _set_auto_status(self, message):
        self._auto_status = message
        if hasattr(self, "lbl_auto_status"):
            self.lbl_auto_status.config(text=f"👁  {message}")

    # ------------------------------------------------------------------
    # Auto-detect: item capture under the cursor
    # ------------------------------------------------------------------
    def _capture_item_at_cursor(self):
        if not VISION_MODULE or not vision.VISION_AVAILABLE:
            self._set_auto_status("Item capture needs the screen-reading modules")
            return
        if not self._active_run_id():
            self._set_auto_status("No run to add an item to")
            return

        name, score, debug = d2r_autodetect.capture_item_at_cursor(
            self.auto_settings, self._item_index
        )
        if name:
            self._add_item(name)
            self._set_auto_status(f"Captured: {vision.strip_suffix(name)} ({score:.0f}%)")
        else:
            self._set_auto_status(f"No match - read: {debug[:60]}")

    def _toggle_session(self):
        if not self.session_running:
            self.session_id = self.db.start_session(self.character_name)
            self.session_start_time = time.time()
            self.session_running = True
            self.last_completed_run_id = None
            self.run_count = 0
            self._sync_session_controls()
            self._sync_run_controls()
            self.lbl_run_count.config(text="Runs this session: 0")
            self.lbl_run_time.config(text="00:00.0", fg=self.ORANGE)
            self.lbl_mini_run_time.config(text="00:00.0", fg=self.ORANGE)
            self.lbl_run_type_active.config(text="")
            self.items_listbox.delete(0, tk.END)
            self.recent_listbox.delete(0, tk.END)
            self._recent_run_map = {}
        else:
            if self.run_running:
                self._toggle_run()
            self.db.end_session(self.session_id)
            self.session_running = False
            self._sync_session_controls()
            self._sync_run_controls()
            self.lbl_session_time.config(text="00:00:00", fg=self.FG)
            self.lbl_mini_session_time.config(text="00:00:00", fg=self.FG)
            self.lbl_run_time.config(text="00:00.0", fg=self.ORANGE)
            self.lbl_mini_run_time.config(text="00:00.0", fg=self.ORANGE)
            self.lbl_run_type_active.config(text="")
            self.current_run_id = None

    def _toggle_run(self, from_detector=False):
        if not self.session_running:
            return

        # A manual start/stop has to be mirrored into the detector, or it will
        # keep waiting for an edge that already happened.
        if not from_detector and self.detector is not None and self.detector.running:
            if self.run_running:
                self.detector.notify_run_stopped_externally()
            else:
                self.detector.notify_run_started_externally()

        if not self.run_running:
            run_type = self.run_type_var.get()
            player_count = self.player_count_var.get()
            self.current_run_id = self.db.start_run(self.session_id, run_type, player_count)
            self.run_start_time = time.time()
            self.run_running = True
            self._sync_run_controls()
            self.lbl_run_type_active.config(text=f"{run_type}  |  {player_count}")
            self.items_listbox.delete(0, tk.END)
            self._item_id_map = {}
        else:
            duration = self.db.end_run(self.current_run_id)
            self.run_running = False
            self.last_completed_run_id = self.current_run_id
            self.current_run_id = None
            self.run_count = self.db.count_completed_runs(self.session_id)
            self.lbl_run_count.config(text=f"Runs this session: {self.run_count}")
            self._sync_run_controls()
            self.lbl_run_time.config(text=self._fmt_run(duration))
            self.lbl_mini_run_time.config(text=self._fmt_run(duration))
            self.lbl_run_type_active.config(text="")
            self._reload_item_list(self.last_completed_run_id)
            self._refresh_recent()

    def _active_run_id(self):
        return self.current_run_id or self.last_completed_run_id

    def _add_item(self, item_name):
        run_id = self._active_run_id()
        if not run_id:
            return
        self.db.add_item(run_id, item_name)
        self._reload_item_list(run_id)
        self._refresh_recent()
        self.item_entry.clear()

    def _remove_item(self):
        selection = self.items_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        item_id = self._item_id_map.get(idx)
        if item_id is not None:
            self.db.delete_item_by_id(item_id)
        run_id = self._active_run_id()
        if run_id:
            self._reload_item_list(run_id)
            self._refresh_recent()

    def _reload_item_list(self, run_id):
        self.items_listbox.delete(0, tk.END)
        self._item_id_map = {}
        if not run_id:
            return
        for i, row in enumerate(self.db.get_run_items(run_id)):
            self.items_listbox.insert(tk.END, f"💎  {row['item_name']}")
            self._item_id_map[i] = row["id"]

    def _refresh_recent(self):
        self.recent_listbox.delete(0, tk.END)
        self._recent_run_map = {}
        if not self.session_id:
            return
        rows = self.db.get_recent_runs(self.session_id, 12)
        for i, row in enumerate(rows):
            duration_text = self._fmt_run(row["duration_seconds"] or 0)
            short = (
                row["run_type"].replace("Hell - ", "H:")
                .replace("NM - ", "NM:")
                .replace("Normal - ", "N:")
            )
            line = f"{short} | {row['player_count']} [{duration_text}]"
            if row["items_found"]:
                line += f"  ->  {row['items_found']}"
            self.recent_listbox.insert(tk.END, line)
            self._recent_run_map[i] = row["id"]

    def _remove_selected_recent_run(self):
        selection = self.recent_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        run_id = self._recent_run_map.get(idx)
        if run_id is None:
            return
        self.db.delete_run(run_id)
        if self.last_completed_run_id == run_id:
            self.last_completed_run_id = None
            self.items_listbox.delete(0, tk.END)
            self._item_id_map = {}
        self.run_count = self.db.count_completed_runs(self.session_id) if self.session_id else 0
        self.lbl_run_count.config(text=f"Runs this session: {self.run_count}")
        self._refresh_recent()

    def _build_scope_data(self, runs, items, scope_duration):
        runs = list(runs)
        items = list(items)

        overall = self._summarize_group(runs, items, scope_duration, total_scope_runs=len(runs))
        groups = []
        grouped_runs = {}
        grouped_items = {}

        for run in runs:
            label = f"{run['run_type']} | {run['player_count']}"
            grouped_runs.setdefault(label, []).append(run)

        for item in items:
            label = f"{item['run_type']} | {item['player_count']}"
            grouped_items.setdefault(label, []).append(item)

        for label in sorted(grouped_runs.keys()):
            groups.append(
                self._summarize_group(
                    grouped_runs[label],
                    grouped_items.get(label, []),
                    scope_duration,
                    label=label,
                    total_scope_runs=len(runs),
                )
            )

        return {"runs": runs, "items": items, "overall": overall, "groups": groups}

    def _summarize_group(self, runs, items, scope_duration, label="Overall", total_scope_runs=None):
        durations = [float(r["duration_seconds"]) for r in runs if r["duration_seconds"] is not None]
        total_runs = len(runs)
        total_run_time = sum(durations)
        avg = total_run_time / total_runs if total_runs else 0.0
        fastest = min(durations) if durations else 0.0
        slowest = max(durations) if durations else 0.0
        item_count = len(items)
        items_per_run = item_count / total_runs if total_runs else 0.0
        runs_per_hour_scope = total_runs / (scope_duration / 3600) if scope_duration > 0 else 0.0
        run_share_pct = (100 * total_runs / total_scope_runs) if total_scope_runs else 0.0

        counts = {}
        for item in items:
            counts[item["item_name"]] = counts.get(item["item_name"], 0) + 1
        item_rates = []
        for name, count in sorted(counts.items(), key=lambda x: (-x[1], x[0].lower()))[:18]:
            pct = (100 * count / total_runs) if total_runs else 0.0
            item_rates.append((name, count, pct))

        return {
            "label": label,
            "run_count": total_runs,
            "item_count": item_count,
            "items_per_run": items_per_run,
            "runs_per_hour_scope": runs_per_hour_scope,
            "run_share_pct": run_share_pct,
            "session_time_text": self._fmt_session(scope_duration),
            "run_time_text": self._fmt_session(total_run_time),
            "avg_run_text": self._fmt_run(avg),
            "fastest_text": self._fmt_run(fastest),
            "slowest_text": self._fmt_run(slowest),
            "item_rates": item_rates,
            "total_runs": total_runs,
        }

    def _scope_duration_for_session(self, session_row):
        if not session_row:
            return 0.0
        start = datetime.fromisoformat(session_row["start_time"])
        end = datetime.fromisoformat(session_row["end_time"]) if session_row["end_time"] else datetime.now()
        return max(0.0, (end - start).total_seconds())

    def _show_stats(self):
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=self.BG)
        x = max(20, self.root.winfo_x() - 80)
        y = max(20, self.root.winfo_y() + 40)
        win.geometry(f"1180x720+{x}+{y}")
        win.resizable(False, False)

        top = tk.Frame(win, bg="#12122a")
        top.pack(fill=tk.X)
        tk.Label(
            top,
            text=f"📊  MF Stats — {self.character_name}",
            font=("Segoe UI", 12, "bold"),
            fg=self.GOLD,
            bg="#12122a",
            padx=8,
            pady=6,
        ).pack(side=tk.LEFT)
        tk.Button(
            top,
            text="✕",
            command=win.destroy,
            font=("Segoe UI", 10),
            bg="#5a1a1a",
            fg=self.FG,
            activebackground="#7a2a2a",
            relief="flat",
            padx=6,
            pady=2,
        ).pack(side=tk.RIGHT, padx=6, pady=4)
        top.bind("<Button-1>", lambda e: self._drag_child_start(e, win))
        top.bind("<B1-Motion>", lambda e: self._drag_child_move(e, win))

        body = tk.Frame(win, bg=self.BG)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        body.grid_columnconfigure(0, weight=1, uniform="stats")
        body.grid_columnconfigure(1, weight=1, uniform="stats")
        body.grid_rowconfigure(0, weight=1)

        current_pane = StatsPane(body, "Current Session", self.BG, self.FG, self.GOLD)
        current_pane.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        alltime_pane = StatsPane(body, "All-Time", self.BG, self.FG, self.GOLD)
        alltime_pane.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        if self.session_id:
            session_row = self.db.get_session_row(self.session_id)
            session_runs = self.db.get_session_runs(self.session_id)
            session_items = self.db.get_session_items(self.session_id)
            session_scope = self._build_scope_data(session_runs, session_items, self._scope_duration_for_session(session_row))
            current_pane.load_scope(session_scope)
        else:
            current_pane.render_empty("No active session.")

        sessions = self.db.get_all_sessions(self.character_name)
        if not sessions:
            alltime_pane.render_empty("No sessions recorded yet.")
        else:
            session_ids = [row["id"] for row in sessions]
            all_runs = self.db.get_all_runs_for_sessions(session_ids)
            all_items = self.db.get_all_items_for_sessions(session_ids)
            total_scope_duration = 0.0
            for row in sessions:
                total_scope_duration += self._scope_duration_for_session(row)
            all_scope = self._build_scope_data(all_runs, all_items, total_scope_duration)
            alltime_pane.load_scope(all_scope)

    def _tick(self):
        if self.session_running and self.session_start_time:
            elapsed = time.time() - self.session_start_time
            session_text = self._fmt_session(elapsed)
            self.lbl_session_time.config(text=session_text, fg=self.GREEN)
            self.lbl_mini_session_time.config(text=session_text, fg=self.GREEN)
        if self.run_running and self.run_start_time:
            elapsed = time.time() - self.run_start_time
            run_text = self._fmt_run(elapsed)
            self.lbl_run_time.config(text=run_text, fg=self.ORANGE)
            self.lbl_mini_run_time.config(text=run_text, fg=self.ORANGE)
        self.root.after(100, self._tick)

    @staticmethod
    def _fmt_session(seconds):
        total = int(round(seconds))
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    @staticmethod
    def _fmt_run(seconds):
        if seconds is None:
            seconds = 0
        m, rem = divmod(int(seconds), 60)
        s = int(rem)
        tenths = int((float(seconds) % 1) * 10)
        return f"{m:02d}:{s:02d}.{tenths}"

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        if self.detector is not None:
            self.detector.stop()
        if self.run_running:
            self._toggle_run()
        if self.session_running and self.db and self.session_id:
            self.db.end_session(self.session_id)
        if self.db:
            self.db.close()
        if GLOBAL_HOTKEYS:
            for handle in self._hotkey_handles:
                try:
                    kb.remove_hotkey(handle)
                except Exception:
                    pass
        self.root.destroy()


if __name__ == "__main__":
    app = D2RMFTracker()
    app.run()
