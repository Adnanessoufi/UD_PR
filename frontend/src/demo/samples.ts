export type Language = 'en' | 'hu'
export type Channel = 'website' | 'linkedin' | 'facebook' | 'instagram' | 'tiktok' | 'youtube'
export type Draft = { title: string; body: string }
type Fact = { id: string; claim: string; excerpt: string; note: string }
type Question = { question: string; answer: string; factId: string }
type Translation = {
  title: string
  summary: string
  sourceTitle: string
  source: string
  article: Draft
  social: string
  facts: Fact[]
  questions: Question[]
}
export type Sample = {
  id: 'research' | 'announcement'
  label: string
  kind: string
  filename: string
  image: string
  video: string
  en: Translation
  hu: Translation
}

// These examples are written for the demo. They contain no real study results or event details.
export const samples: Sample[] = [
  {
    id: 'research',
    label: 'A quieter place to study',
    kind: 'Research paper',
    filename: 'sample-study-notes.txt',
    image: '/demo/study-poster.svg',
    video: '/demo/study-walkthrough.mp4',
    en: {
      title: 'A quieter place to study',
      summary: 'A small study, a clear story, and a limitation worth keeping in the headline.',
      sourceTitle: 'Quiet study spaces: notes from a small pilot',
      source:
        'FICTIONAL SOURCE. Prepared for the UD PR Studio demo.\n\n[1] A four-week pilot offered a quiet study room to 24 student volunteers.\n\n[2] At the end of the pilot, 18 of the 24 volunteers said the room helped them concentrate. This was a self-reported response.\n\n[3] The pilot had no control group and did not measure grades or exam performance. It cannot establish that the room caused better academic results.',
      article: {
        title: 'Quiet study room gets positive feedback in a small pilot',
        body: 'A quiet place to study may sound like a small thing. In this fictional four-week pilot, 24 student volunteers were given access to a quiet study room.\n\nAt the end, 18 said the room helped them concentrate. That tells us how those students felt about the space. It does not tell us whether their grades improved.\n\nThe pilot had no control group and did not measure exam performance. A larger study would be needed before making claims about academic results.',
      },
      social:
        'Would a quieter room help you study? In this fictional four-week pilot, 18 of 24 student volunteers said it helped them concentrate.\n\nThat is feedback from a small group, not evidence of better grades. There was no control group, and exam performance was not measured.',
      facts: [
        {
          id: 'F1',
          claim: '24 volunteers took part over four weeks.',
          excerpt: 'A four-week pilot offered a quiet study room to 24 student volunteers.',
          note: 'The sample size and duration match source section 1.',
        },
        {
          id: 'F2',
          claim: '18 volunteers said the room helped them concentrate.',
          excerpt:
            'At the end of the pilot, 18 of the 24 volunteers said the room helped them concentrate. This was a self-reported response.',
          note: 'The draft keeps the result as self-reported feedback.',
        },
        {
          id: 'F3',
          claim: 'The pilot cannot establish better academic results.',
          excerpt: 'The pilot had no control group and did not measure grades or exam performance.',
          note: 'The limitation stays in the article and social drafts.',
        },
      ],
      questions: [
        {
          question: 'Did their grades improve?',
          answer:
            'The source does not answer that. The pilot did not measure grades or exam performance, so we cannot claim an improvement.',
          factId: 'F3',
        },
        {
          question: 'How many students took part?',
          answer:
            '24 student volunteers took part in the four-week pilot. This is a fictional example prepared for the demo.',
          factId: 'F1',
        },
        {
          question: 'What did the students actually report?',
          answer:
            '18 of the 24 volunteers said the room helped them concentrate. This was their own feedback, not an objective measure of concentration.',
          factId: 'F2',
        },
      ],
    },
    hu: {
      title: 'Csendesebb hely a tanuláshoz',
      summary: 'Egy kis létszámú vizsgálat és egy fontos korlát, amelyet a szöveg is megőriz.',
      sourceTitle: 'Csendes tanulóhelyek: egy kísérleti vizsgálat jegyzetei',
      source:
        'KITALÁLT FORRÁS. Az UD PR Studio bemutatójához készült.\n\n[1] Egy négyhetes kísérleti vizsgálatban 24 önként jelentkező hallgató használhatott egy csendes tanulószobát.\n\n[2] A vizsgálat végén a 24 résztvevő közül 18 azt mondta, hogy a szoba segítette az összpontosításban. Ez önbevalláson alapuló visszajelzés volt.\n\n[3] Nem volt kontrollcsoport, és nem mérték a jegyeket vagy a vizsgaeredményeket. A vizsgálat nem bizonyítja, hogy a szoba jobb tanulmányi eredményeket okozott.',
      article: {
        title: 'Pozitív visszajelzések a csendes tanulószobáról egy kis létszámú vizsgálatban',
        body: 'Ebben a kitalált, négyhetes kísérleti vizsgálatban 24 önként jelentkező hallgató használhatott egy csendes tanulószobát.\n\nA végén 18 résztvevő azt mondta, hogy a szoba segítette az összpontosításban. Ez azt mutatja meg, hogyan élték meg a hallgatók a tanulást ebben a térben. Arról nem ad választ, hogy javultak-e a jegyeik.\n\nNem volt kontrollcsoport, és a vizsgaeredményeket sem mérték. A tanulmányi eredményekre gyakorolt hatás megállapításához nagyobb vizsgálatra lenne szükség.',
      },
      social:
        'Segítene egy csendesebb szoba a tanulásban? Ebben a kitalált, négyhetes vizsgálatban 24 önkéntes hallgatóból 18 szerint igen.\n\nEz egy kis csoport visszajelzése. Nem bizonyít jobb jegyeket: nem volt kontrollcsoport, és a vizsgaeredményeket sem mérték.',
      facts: [
        {
          id: 'F1',
          claim: '24 önkéntes vett részt a négyhetes vizsgálatban.',
          excerpt:
            'Egy négyhetes kísérleti vizsgálatban 24 önként jelentkező hallgató használhatott egy csendes tanulószobát.',
          note: 'A létszám és az időtartam megegyezik a forrás 1. részével.',
        },
        {
          id: 'F2',
          claim: '18 résztvevő szerint a szoba segítette az összpontosítást.',
          excerpt:
            'A vizsgálat végén a 24 résztvevő közül 18 azt mondta, hogy a szoba segítette az összpontosításban. Ez önbevalláson alapuló visszajelzés volt.',
          note: 'A szöveg önbevalláson alapuló visszajelzésként mutatja be az eredményt.',
        },
        {
          id: 'F3',
          claim: 'A vizsgálat nem bizonyít jobb tanulmányi eredményeket.',
          excerpt: 'Nem volt kontrollcsoport, és nem mérték a jegyeket vagy a vizsgaeredményeket.',
          note: 'A korlát a cikkben és a közösségi bejegyzésekben is szerepel.',
        },
      ],
      questions: [
        {
          question: 'Javultak a jegyeik?',
          answer:
            'Erre a forrás nem ad választ. Nem mérték a jegyeket vagy a vizsgaeredményeket, ezért javulást sem állíthatunk.',
          factId: 'F3',
        },
        {
          question: 'Hány hallgató vett részt?',
          answer:
            '24 önkéntes hallgató vett részt a négyhetes vizsgálatban. Ez a bemutatóhoz készített kitalált példa.',
          factId: 'F1',
        },
        {
          question: 'Miről számoltak be a hallgatók?',
          answer:
            'A 24 résztvevő közül 18 szerint a szoba segítette az összpontosítást. Ez saját visszajelzésük volt, nem az összpontosítás objektív mérése.',
          factId: 'F2',
        },
      ],
    },
  },
  {
    id: 'announcement',
    label: 'An evening of student projects',
    kind: 'Short announcement',
    filename: 'sample-event-brief.txt',
    image: '/demo/event-poster.svg',
    video: '/demo/event-walkthrough.mp4',
    en: {
      title: 'An evening of student projects',
      summary: 'A short announcement, adapted for the places students actually read.',
      sourceTitle: 'Student project evening: sample event brief',
      source:
        'FICTIONAL SOURCE. This event does not exist. Prepared for the UD PR Studio demo.\n\n[1] The sample student project evening is scheduled for 21 November 2026, from 17:00 to 19:00.\n\n[2] The fictional venue is the East Campus project room. Entry is free, and registration is not required.\n\n[3] Visitors can meet student teams and try their project demos. No speakers, sponsors or prizes have been announced.',
      article: {
        title: 'Meet the teams behind the student projects',
        body: 'This sample event brings student teams together for an evening of project demos. Visitors can meet the teams and try what they have made.\n\nThe fictional event is scheduled for 21 November 2026, from 17:00 to 19:00, in the East Campus project room. Entry is free and no registration is needed.\n\nThis is an example announcement for the demo. There is no real event to attend, and no speakers, sponsors or prizes have been announced.',
      },
      social:
        'See what student teams have been working on. Meet the teams and try their demos.\n\nSample event: 21 November 2026, 17:00–19:00. East Campus project room. Free entry, no registration.\n\nFictional example for UD PR Studio. This is not a real event invitation.',
      facts: [
        {
          id: 'F1',
          claim: 'The sample event runs on 21 November, 17:00 to 19:00.',
          excerpt:
            'The sample student project evening is scheduled for 21 November 2026, from 17:00 to 19:00.',
          note: 'The date and times match source section 1.',
        },
        {
          id: 'F2',
          claim: 'Free entry, with no registration.',
          excerpt:
            'The fictional venue is the East Campus project room. Entry is free, and registration is not required.',
          note: 'The draft keeps the entry details from the brief.',
        },
        {
          id: 'F3',
          claim: 'Visitors can meet teams and try project demos.',
          excerpt:
            'Visitors can meet student teams and try their project demos. No speakers, sponsors or prizes have been announced.',
          note: 'The draft adds no speakers, sponsors or prizes.',
        },
      ],
      questions: [
        {
          question: 'Do I need to register?',
          answer:
            'In the sample brief, entry is free and registration is not required. This is a fictional event used to demonstrate the workflow.',
          factId: 'F2',
        },
        {
          question: 'When is it?',
          answer:
            'The sample brief says 21 November 2026, from 17:00 to 19:00. There is no real event to attend.',
          factId: 'F1',
        },
        {
          question: 'Are there any prizes?',
          answer: 'The brief does not announce any prizes. The draft should not add them.',
          factId: 'F3',
        },
      ],
    },
    hu: {
      title: 'Hallgatói projektek estéje',
      summary: 'Egy rövid bejelentés, a hallgatók által használt csatornákra átdolgozva.',
      sourceTitle: 'Hallgatói projektek estéje: minta eseményleírás',
      source:
        'KITALÁLT FORRÁS. Ez az esemény nem létezik. Az UD PR Studio bemutatójához készült.\n\n[1] A mintaesemény időpontja 2026. november 21., 17:00–19:00.\n\n[2] A kitalált helyszín az East Campus projektterme. A belépés ingyenes, regisztráció nem szükséges.\n\n[3] A látogatók megismerhetik a hallgatói csapatokat és kipróbálhatják a projektjeiket. Előadókat, támogatókat és díjakat nem jelentettek be.',
      article: {
        title: 'Ismerd meg a hallgatói projektek mögött álló csapatokat',
        body: 'A mintaesemény egy estére hozza össze a hallgatói csapatokat. A látogatók megismerhetik őket és kipróbálhatják a projektjeiket.\n\nA kitalált esemény időpontja 2026. november 21., 17:00–19:00, helyszíne az East Campus projektterme. A belépés ingyenes, és regisztráció sem kell.\n\nEz a bemutatóhoz készült példaszöveg. Nincs valódi esemény, amelyre el lehet menni. Előadókat, támogatókat és díjakat nem jelentettek be.',
      },
      social:
        'Nézd meg, min dolgoznak a hallgatói csapatok. Ismerd meg őket és próbáld ki a projektjeiket.\n\nMintaesemény: 2026. november 21., 17:00–19:00. East Campus projektterem. Ingyenes belépés, regisztráció nélkül.\n\nKitalált példa az UD PR Studio bemutatójához. Ez nem valódi meghívó.',
      facts: [
        {
          id: 'F1',
          claim: 'A mintaesemény november 21-én, 17:00–19:00 között van.',
          excerpt: 'A mintaesemény időpontja 2026. november 21., 17:00–19:00.',
          note: 'A dátum és az időpont megegyezik a forrás 1. részével.',
        },
        {
          id: 'F2',
          claim: 'Ingyenes belépés, regisztráció nélkül.',
          excerpt:
            'A kitalált helyszín az East Campus projektterme. A belépés ingyenes, regisztráció nem szükséges.',
          note: 'A szöveg megőrzi az eseményleírás belépési feltételeit.',
        },
        {
          id: 'F3',
          claim: 'A látogatók megismerhetik a csapatokat és a projektjeiket.',
          excerpt:
            'A látogatók megismerhetik a hallgatói csapatokat és kipróbálhatják a projektjeiket. Előadókat, támogatókat és díjakat nem jelentettek be.',
          note: 'A szöveg nem ad hozzá előadókat, támogatókat vagy díjakat.',
        },
      ],
      questions: [
        {
          question: 'Kell regisztrálni?',
          answer:
            'A minta szerint a belépés ingyenes, és regisztráció nem kell. Ez a munkafolyamatot bemutató kitalált esemény.',
          factId: 'F2',
        },
        {
          question: 'Mikor lesz?',
          answer:
            'A minta szerint 2026. november 21-én, 17:00 és 19:00 között. Nincs valódi esemény, amelyre el lehet menni.',
          factId: 'F1',
        },
        {
          question: 'Lesznek díjak?',
          answer: 'A leírás nem jelent be díjakat. A szövegnek sem szabad hozzáadnia őket.',
          factId: 'F3',
        },
      ],
    },
  },
]

export const channels: { id: Channel; label: string; mark: string }[] = [
  { id: 'website', label: 'Website', mark: 'W' },
  { id: 'linkedin', label: 'LinkedIn', mark: 'in' },
  { id: 'facebook', label: 'Facebook', mark: 'f' },
  { id: 'instagram', label: 'Instagram', mark: '◎' },
  { id: 'tiktok', label: 'TikTok', mark: '♪' },
  { id: 'youtube', label: 'YouTube', mark: '▶' },
]

export function sampleDraft(sample: Sample, language: Language, channel: Channel): Draft {
  const text = sample[language]
  if (channel === 'website') return { ...text.article }
  const tag = channel === 'instagram' ? '\n\n#StudentProjects #UniversityLife' : ''
  const videoNote =
    channel === 'youtube' || channel === 'tiktok'
      ? language === 'hu'
        ? '\n\nA mellékelt mintavideó angol nyelvű.'
        : '\n\nThe sample video uses English narration.'
      : ''
  return { title: text.article.title, body: text.social + tag + videoNote }
}
