import fs from 'fs/promises';
import path from 'path';
import { openApp } from './session.js';

const APP_ID = process.env.APP_ID || 'MyApp.qvf';
const OUT_DIR = process.env.OUT_DIR || './output';

// --- helpers ---------------------------------------------------------------

// Generic "get all objects of these types" via the app's object list.
async function listObjects(doc, qTypes) {
  const sessionObj = await doc.createSessionObject({
    qInfo: { qType: 'ObjectList' },
    qAppObjectListDef: { qType: qTypes[0], qData: { title: '/qMetaDef/title' } },
  });
  const layout = await sessionObj.getLayout();
  return layout.qAppObjectList.qItems || [];
}

// Pull a single object's full property tree + computed layout.
async function dumpObject(doc, id) {
  const obj = await doc.getObject(id);
  const [properties, layout] = await Promise.all([
    obj.getFullPropertyTree().catch(() => obj.getProperties()),
    obj.getLayout().catch(() => null),
  ]);
  return { id, obj, properties, layout };
}

// Children of a sheet may live in the property tree (qChildren) OR, when the
// tree call falls back to getProperties(), not be present at all. As a
// backstop, enumerate them via getChildInfos() and fetch each directly.
async function resolveChildren(doc, sheetObj) {
  const fromTree = (sheetObj.properties?.qChildren || []).map((c) => ({
    id: c.qProperty?.qInfo?.qId,
    type: c.qProperty?.qInfo?.qType,
    props: c.qProperty,
  }));
  if (fromTree.length) return fromTree;

  // Backstop: ask the handle for its children and load each.
  try {
    const infos = await sheetObj.obj.getChildInfos();
    return Promise.all(
      (infos || []).map(async (info) => {
        try {
          const child = await doc.getObject(info.qId);
          const props = await child.getProperties();
          return { id: info.qId, type: info.qType || props?.qInfo?.qType, props };
        } catch {
          return { id: info.qId, type: info.qType, props: null };
        }
      })
    );
  } catch {
    return [];
  }
}

// --- extraction stages -----------------------------------------------------

async function extractScript(doc) {
  // The full load script — the most important artifact for migration.
  return doc.getScript();
}

async function extractDataModel(doc) {
  // Tables, fields, keys, and associations as the engine sees them post-reload.
  const tablesAndKeys = await doc.getTablesAndKeys(
    { qcx: 1000, qcy: 1000 }, // window size for layout
    { qcx: 0, qcy: 0 },
    30,    // max tables
    true,  // include system tables
    false  // include only synthetic = false
  );
  return tablesAndKeys;
}

async function extractMasterItems(doc) {
  const [measures, dimensions] = await Promise.all([
    listObjects(doc, ['measure']),
    listObjects(doc, ['dimension']),
  ]);

  const expand = async (items, getter) =>
    Promise.all(items.map(async (it) => {
      const h = await getter(it.qInfo.qId);
      const props = await h.getProperties();
      return { id: it.qInfo.qId, props };
    }));

  return {
    measures: await expand(measures, (id) => doc.getMeasure(id)),
    dimensions: await expand(dimensions, (id) => doc.getDimension(id)),
  };
}

async function extractSheetsAndCharts(doc) {
  const sheets = await listObjects(doc, ['sheet']);
  const result = [];
  for (const sheet of sheets) {
    const sheetObj = await dumpObject(doc, sheet.qInfo.qId);
    const children = await resolveChildren(doc, sheetObj);
    result.push({
      id: sheet.qInfo.qId,
      title: sheet.qMeta?.title,
      properties: sheetObj.properties,
      children,
    });
  }
  return result;
}

// --- orchestration ---------------------------------------------------------

async function main() {
  await fs.mkdir(OUT_DIR, { recursive: true });

  console.log(`Opening ${APP_ID} ...`);
  const { session, doc } = await openApp(APP_ID);

  try {
    console.log('Extracting load script ...');
    const script = await extractScript(doc);
    await fs.writeFile(path.join(OUT_DIR, 'script.qvs'), script, 'utf8');

    console.log('Extracting data model ...');
    const dataModel = await extractDataModel(doc);
    await fs.writeFile(
      path.join(OUT_DIR, 'data-model.json'),
      JSON.stringify(dataModel, null, 2),
    );

    console.log('Extracting master items ...');
    const masterItems = await extractMasterItems(doc);
    await fs.writeFile(
      path.join(OUT_DIR, 'master-items.json'),
      JSON.stringify(masterItems, null, 2),
    );

    console.log('Extracting sheets and charts ...');
    const sheets = await extractSheetsAndCharts(doc);
    await fs.writeFile(
      path.join(OUT_DIR, 'sheets.json'),
      JSON.stringify(sheets, null, 2),
    );

    // Single consolidated manifest for downstream TML generation.
    await fs.writeFile(
      path.join(OUT_DIR, 'manifest.json'),
      JSON.stringify(
        {
          app: APP_ID,
          extractedAt: new Date().toISOString(),
          counts: {
            sheets: sheets.length,
            measures: masterItems.measures.length,
            dimensions: masterItems.dimensions.length,
            tables: dataModel.qtr?.length ?? 0,
          },
        },
        null,
        2,
      ),
    );

    console.log(`Done. Artifacts written to ${OUT_DIR}/`);
    console.log('Feed this folder to q2t:  python -m q2t extract --mode engine-artifacts --artifacts ' + OUT_DIR);
  } finally {
    await session.close();
  }
}

main().catch((err) => {
  console.error('Extraction failed:', err);
  process.exit(1);
});
