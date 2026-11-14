/**
 * Creates the TM-BraessGreen citizen survey as a Google Form, plus a linked response sheet.
 *
 * How to run:
 *   1. Go to https://script.google.com -> New project.
 *   2. Paste this whole file into Code.gs and save.
 *   3. Select `createSurvey` in the toolbar and click Run. Accept the permissions prompt.
 *   4. Open View -> Logs (or Execution log): it prints the public link, the edit link and the sheet link.
 *
 * The form is anonymous: it does not collect e-mail addresses. Running the function again creates
 * a NEW form, so run it once and edit the result in the Forms UI afterwards.
 */

var NEIGHBOURHOODS = [
  'Bălcescu',
  'Blașcovici',
  'Bucovina',
  'Calea Aradului',
  'Calea Buziașului',
  'Calea Girocului',
  'Calea Lipovei',
  'Calea Martirilor',
  'Calea Șagului',
  'Calea Torontalului',
  'Cetate',
  'Ciarda Roșie',
  'Circumvalațiunii',
  'Complexul Studențesc',
  'Dâmbovița',
  'Elisabetin',
  'Fabric',
  'Fratelia',
  'Freidorf',
  'Ghiroda Nouă',
  'Ion Ionescu de la Brad',
  'Iosefin',
  'Kuncz',
  'Mehala',
  'Plopi',
  'Ronaț',
  'Soarelui',
  'Steaua',
  'Tipografilor',
  'Alt cartier din Timișoara',
  'Zona metropolitană (Dumbrăvița, Giroc, Moșnița, Ghiroda etc.)',
  'Nu locuiesc în Timișoara'
];

function createSurvey() {
  var form = FormApp.create('Traficul din Timișoara: cum vă deplasați?');

  form.setDescription(
    'Suntem o echipă de studenți la UniHack 2026 și construim un simulator de trafic pentru Timișoara, ' +
    'care arată ce se întâmplă cu traficul și cu transportul public când se schimbă benzile unei străzi.\n\n' +
    'Răspunsurile dumneavoastră ne ajută să verificăm valorile pe care le folosim în calcule. ' +
    'Chestionarul durează aproximativ 2 minute și este complet anonim: nu colectăm nume, adrese de e-mail ' +
    'sau alte date personale. Răspunsurile sunt folosite doar pentru acest proiect.'
  );
  try { form.setCollectEmail(false); } catch (e) { /* not available on every account type */ }
  form.setProgressBar(true);
  form.setShowLinkToRespondAgain(false);
  form.setConfirmationMessage('Vă mulțumim! Răspunsurile dumneavoastră ne ajută să facem simulatorul mai precis.');

  // 0. Where they live, and whether they know the corridor
  form.addListItem()
    .setTitle('În ce cartier locuiți?')
    .setChoiceValues(NEIGHBOURHOODS)
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Cât de des treceți prin zona Calea Martirilor / Strada Cluj?')
    .setChoiceValues(['Zilnic', 'Săptămânal', 'Rar', 'Niciodată'])
    .setRequired(true);

  // 1. The hook (keep it before any question that hints at the answer)
  form.addMultipleChoiceItem()
    .setTitle('Dacă Primăria închide circulației o stradă laterală scurtă, ce se întâmplă cu traficul total din zonă?')
    .setChoiceValues(['Se înrăutățește', 'Rămâne la fel', 'Se îmbunătățește', 'Depinde'])
    .setRequired(true);

  // 2. Mode share (checks the 44 % car share)
  form.addMultipleChoiceItem()
    .setTitle('Cum ajungeți de obicei la serviciu sau la facultate?')
    .setChoiceValues([
      'Conduc mașina',
      'Sunt pasager într-o mașină',
      'Cu autobuzul, tramvaiul sau troleibuzul',
      'Cu bicicleta sau trotineta',
      'Pe jos',
      'Nu fac naveta (lucrez sau învăț de acasă)'
    ])
    .showOtherOption(true)
    .setRequired(true);

  // 3. Car occupancy (checks 1.3 people per car)
  form.addMultipleChoiceItem()
    .setTitle('Când mergeți cu mașina, câte persoane sunt de obicei în ea (inclusiv dumneavoastră)?')
    .setChoiceValues(['1', '2', '3 sau mai multe', 'Nu merg cu mașina'])
    .setRequired(true);

  // 4. Departure time (checks the 07:30–08:30 peak window)
  form.addMultipleChoiceItem()
    .setTitle('La ce oră plecați de obicei de acasă dimineața?')
    .setChoiceValues(['Înainte de 7:00', '7:00–7:30', '7:30–8:30', 'După 8:30', 'Nu plec la o oră fixă dimineața'])
    .setRequired(true);

  // 5. Navigation apps (evidence for selfish routing, the mechanism behind Braess)
  form.addMultipleChoiceItem()
    .setTitle('Folosiți Waze sau Google Maps când conduceți prin oraș?')
    .setChoiceValues(['Mereu', 'Uneori', 'Niciodată', 'Nu conduc'])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Urmați scurtăturile prin străzi laterale pe care vi le sugerează aplicația?')
    .setChoiceValues(['Mereu', 'Uneori', 'Niciodată', 'Nu folosesc astfel de aplicații', 'Nu conduc'])
    .setRequired(true);

  // 6. Cut-through streets (do NOT name any streets here, it would bias the answers)
  form.addMultipleChoiceItem()
    .setTitle('Vi se întâmplă să ocoliți Calea Martirilor sau Strada Cluj pe străzi laterale?')
    .setChoiceValues(['Da', 'Nu', 'Nu circul prin zonă'])
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('Dacă da, pe ce străzi?')
    .setHelpText('Opțional.')
    .setRequired(false);

  // 7. Switching ladder
  form.addMultipleChoiceItem()
    .setTitle('Dacă o bandă dedicată ar face drumul dumneavoastră cu autobuzul sau troleibuzul mai rapid decât cu mașina, ' +
              'cu cât ar trebui să fie mai rapid ca să renunțați la mașină?')
    .setChoiceValues([
      '2 minute',
      '5 minute',
      '10 minute',
      '15 minute sau mai mult',
      'N-aș renunța niciodată la mașină',
      'Folosesc deja transportul public',
      'Nu am mașină'
    ])
    .setRequired(true);

  // Response sheet
  var sheet = SpreadsheetApp.create('Răspunsuri - Traficul din Timișoara');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());

  Logger.log('Public link (share this): ' + form.getPublishedUrl());
  Logger.log('Edit link (team only):    ' + form.getEditUrl());
  Logger.log('Responses sheet:          ' + sheet.getUrl());
}
