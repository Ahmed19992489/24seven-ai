// ==========================================
// 24Seven - Google Apps Script Web App
// ==========================================

const SHEET_ID = '1-YglRYU8RZ6fl8xoWBNgxiV5IRna4KgE8ynpjsjtCD4';
const SHEET_TAB = 'امر حجز عميل';

function doPost(e) {
    try {
        const data = JSON.parse(e.postData.contents);
        
        if (data.action === 'assignDriver') {
            var debugInfo = updateDriverInSheet(data);
            return ContentService
                .createTextOutput(JSON.stringify({ success: true, debug: debugInfo }))
                .setMimeType(ContentService.MimeType.JSON);
        } else {
            appendBookingToSheet(data);
        }
        
        return ContentService
            .createTextOutput(JSON.stringify({ success: true }))
            .setMimeType(ContentService.MimeType.JSON);
    } catch (err) {
        return ContentService
            .createTextOutput(JSON.stringify({ success: false, error: err.toString() }))
            .setMimeType(ContentService.MimeType.JSON);
    }
}

function doGet(e) {
    return ContentService
        .createTextOutput(JSON.stringify({ status: 'ok', message: '24Seven API running' }))
        .setMimeType(ContentService.MimeType.JSON);
}

function appendBookingToSheet(data) {
    // ... existing setup ...
    const ss = SpreadsheetApp.openById(SHEET_ID);
    const sheet = ss.getSheetByName(SHEET_TAB);
    if (!sheet) throw new Error('الشيت "' + SHEET_TAB + '" غير موجود');

    // ... (rest of formatting) ...
    // Note: Re-using logic but focusing on the row array
    const now = new Date();
    const timestamp = Utilities.formatDate(now, 'Africa/Cairo', 'yyyy/MM/dd HH:mm:ss');
    let formattedDate = (data.tripDate || '').replace(/-/g, '/');
    let formattedTime = data.tripTime || ''; // Should be pre-formatted from client
    
    const row = [
        timestamp,      // A (1)
        formattedDate,  // B (2)
        formattedTime,  // C (3)
        data.clientName || '',
        data.phone || '',
        data.whatsapp || '',
        data.pickup || '',
        data.dropoff || '',
        data.passengers || '1',
        data.bags || '0',
        data.carType || '',
        data.clientStatus || 'عميل ويب',
        data.price || '',
        data.email || '',
        data.notes || '',
        data.tripType || '',
        data.webId || '',              // Q (17) - PERMANENT WEB REFERENCE
        data.enteredBy || 'ويب سايت',  // R (18)
        '', '', 
        data.sqlId || '',              // U (21) - Managed by import_reservations
        '', '', '', '', '', '', '', '', '', '', '', '', '', '',
        'pending'
    ];

    const newRow = sheet.getLastRow() + 1;
    sheet.appendRow(row);
    sheet.getRange(newRow, 5).setNumberFormat('@');
    sheet.getRange(newRow, 6).setNumberFormat('@');
    sheet.getRange(newRow, 17).setNumberFormat('@'); // Force text for Web_ID
    Logger.log('✅ Appended booking with Web_ID: ' + data.webId);
}

function updateDriverInSheet(data) {
    const ss = SpreadsheetApp.openById(SHEET_ID);
    const sheet = ss.getSheetByName(SHEET_TAB);
    if (!sheet) throw new Error('الشيت غير موجود');

    const webId = data.webId;
    const sqlId = data.sqlId;
    const rowHint = parseInt(data.sheetRow);
    let rowNum = 0;
    
    Logger.log('🔍 Processing Assign: RowHint=' + rowHint + ', WebID=' + webId + ', SQLID=' + sqlId);

    // 1. PRIMARY SEARCH: By Web_ID (Column Q / 17) - Highly reliable for newer records
    if (webId) {
        Logger.log('   -> Searching by WebID in Column Q...');
        const lastRow = sheet.getLastRow();
        if (lastRow > 1) {
            const values = sheet.getRange(2, 17, lastRow - 1, 1).getValues();
            for (let i = 0; i < values.length; i++) {
                if (String(values[i][0]).trim() === String(webId).trim()) {
                    rowNum = i + 2;
                    Logger.log('   ✅ Found by WebID at row ' + rowNum);
                    break;
                }
            }
        }
    }

    // 2. SECONDARY SEARCH: By SQL_ID (Column U / 21) - Crucial for old/synced records
    if (!rowNum && sqlId) {
        Logger.log('   -> Searching by SQLID in Column U...');
        const lastRow = sheet.getLastRow();
        if (lastRow > 1) {
            const values = sheet.getRange(2, 21, lastRow - 1, 1).getValues();
            for (let i = 0; i < values.length; i++) {
                const currentVal = String(values[i][0]).trim();
                const targetVal = String(sqlId).trim();
                if (currentVal === targetVal && targetVal !== "") {
                    rowNum = i + 2;
                    Logger.log('   ✅ Found by SQLID at row ' + rowNum);
                    break;
                }
            }
        }
    }

    // 3. TERTIARY FALLBACK: Trust the rowHint if IDs failed (last resort)
    if (!rowNum && rowHint >= 2) {
        Logger.log('   ⚠️ No ID match. Using rowHint: ' + rowHint);
        rowNum = rowHint;
    }

    if (!rowNum || rowNum < 2) {
        Logger.log('   ❌ NOT FOUND');
        throw new Error('تعذر العثور على الحجز (Web_ID: ' + webId + ', SQL_ID: ' + sqlId + ') - تأكد من وجود المعرف في الشيت');
    }

    // Final check to prevent writing to a random row if index is too high
    if (rowNum > sheet.getLastRow() + 10) {
         throw new Error('رقم الصف المكتشف (' + rowNum + ') غير منطقي مقارنة بحجم الشيت');
    }

    // 5. Update data - Columns 22 (V) through 25 (Y)
    var driverName = data.driverName || '';
    var driverPhone = String(data.driverPhone || '');
    var amountPaid = data.amountPaid || '';
    
    // Set phone column as text format first
    sheet.getRange(rowNum, 23).setNumberFormat('@');
    
    // Write all 4 columns at once
    var updateRange = sheet.getRange(rowNum, 22, 1, 4);
    updateRange.setValues([[
      driverName,                     // Col 22 (V) - اسم السائق
      driverPhone,                    // Col 23 (W) - هاتف السائق
      amountPaid,                     // Col 24 (X) - النقدية المستلمة
      ""                              // Col 25 (Y) - نفرغها ليقوم python بإرسال الرسائل
    ]]);

    // Return debug info
    var lastRow = sheet.getLastRow();
    var verifyVal = sheet.getRange(rowNum, 22).getValue();
    return {
      foundRow: rowNum,
      lastRow: lastRow,
      wrote: driverName,
      verified: String(verifyVal)
    };
}
