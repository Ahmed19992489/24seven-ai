// ==========================================
// 24Seven - Google Apps Script Web App
// ==========================================

const SHEET_ID = '1-YglRYU8RZ6fl8xoWBNgxiV5IRna4KgE8ynpjsjtCD4';
const SHEET_TAB = 'امر حجز عميل';

function doPost(e) {
    try {
        const data = JSON.parse(e.postData.contents);
        
        if (data.action === 'assignDriver') {
            updateDriverInSheet(data);
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
    const ss = SpreadsheetApp.openById(SHEET_ID);
    const sheet = ss.getSheetByName(SHEET_TAB);
    if (!sheet) throw new Error('الشيت "' + SHEET_TAB + '" غير موجود');

    const now = new Date();
    const timestamp = Utilities.formatDate(now, 'Africa/Cairo', 'yyyy/MM/dd HH:mm:ss');

    // تنسيق التاريخ: 2026/02/18
    let formattedDate = data.tripDate || '';
    formattedDate = formattedDate.replace(/-/g, '/');

    // تنسيق الوقت: ص 10:00:00
    let formattedTime = data.tripTime || '';
    if (formattedTime) {
        const parts = formattedTime.split(':');
        const hour = parseInt(parts[0]);
        const minute = parts[1] || '00';
        const ampm = hour < 12 ? 'ص' : 'م';
        const hour12 = hour === 0 ? 12 : (hour > 12 ? hour - 12 : hour);
        formattedTime = ampm + ' ' + String(hour12).padStart(2, '0') + ':' + minute + ':00';
    }

    // التليفون مع الصفر
    let phone = String(data.phone || '').trim().replace(/\s/g, '');
    if (phone && !phone.startsWith('0') && phone.length === 10) phone = '0' + phone;
    let whats = String(data.whatsapp || data.phone || '').trim().replace(/\s/g, '');
    if (whats && !whats.startsWith('0') && whats.length === 10) whats = '0' + whats;

    const carTypeMap = { 'sedan': 'سيدان', 'suv': 'SUV (عائلية)', 'van': 'H1 فان', 'limo': 'ليموزين' };
    const tripTypeMap = { 'one-way': 'ذهاب فقط', 'round-diff': 'ذهاب وعودة', 'airport': 'استقبال مطار' };

    const row = [
        timestamp,
        formattedDate,
        formattedTime,
        data.clientName || '',
        phone,
        whats,
        data.pickup || '',
        data.dropoff || '',
        data.passengers || '1',
        data.bags || '0',
        carTypeMap[data.carType] || data.carType || '',
        data.clientStatus || 'عميل ويب',
        data.price || '',
        data.email || '',
        data.notes || '',
        tripTypeMap[data.tripType] || data.tripType || '',
        '',
        data.enteredBy || 'ويب سايت',
        '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '',
        'pending'
    ];

    // إجبار خلايا الهاتف على تنسيق نص
    const newRow = sheet.getLastRow() + 1;
    sheet.appendRow(row);
    sheet.getRange(newRow, 5).setNumberFormat('@');  // رقم الهاتف
    sheet.getRange(newRow, 6).setNumberFormat('@');  // رقم اتساب
    sheet.getRange(newRow, 5).setValue(phone);
    sheet.getRange(newRow, 6).setValue(whats);

    Logger.log('✅ ' + data.clientName + ' | ' + formattedDate + ' ' + formattedTime + ' | ' + phone);
}


function updateDriverInSheet(data) {
    const ss = SpreadsheetApp.openById(SHEET_ID);
    const sheet = ss.getSheetByName(SHEET_TAB);
    if (!sheet) throw new Error('الشيت غير موجود');

    let rowNum = parseInt(data.sheetRow);
    const sqlId = data.sqlId;

    // Fallback search by SQL_ID (Column U / 21)
    if ((!rowNum || rowNum < 2) && sqlId) {
        const lastRow = sheet.getLastRow();
        if (lastRow > 1) {
            const values = sheet.getRange(2, 21, lastRow - 1, 1).getValues();
            for (let i = 0; i < values.length; i++) {
                const rowVal = String(values[i][0]).trim();
                const targetId = String(sqlId).trim();
                if (rowVal === targetId && targetId !== "") {
                    rowNum = i + 2;
                    break;
                }
            }
        }
    }

    if (!rowNum || rowNum < 2) {
        throw new Error('تعذر العثور على الحجز (Row: ' + data.sheetRow + ', SQL_ID: ' + sqlId + ')');
    }

    // Update Columns V (22) and W (23)
    sheet.getRange(rowNum, 22).setValue(data.driverName || '');
    sheet.getRange(rowNum, 23).setNumberFormat('@'); // Force text for phone
    sheet.getRange(rowNum, 23).setValue(String(data.driverPhone || ''));

    Logger.log('✅ Updated row ' + rowNum + ' with driver ' + data.driverName);
}
