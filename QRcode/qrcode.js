import QRCode from 'qrcode';
import fs from 'fs';

const qrCodeString = '00020101021238540010A00000072701240006970415011009876487170208QRIBFTTA53037045405790005802VN62220818Ung Ho Quy Vac Xin6304CD8F';

// Tạo QR code với size 41x41
QRCode.toDataURL(qrCodeString, {
  errorCorrectionLevel: 'L',
  version: 5, // Version 5 tạo matrix 37x37
  margin: 0,
  width: 410 // Độ phân giải cao để dễ đọc
}, (err, url) => {
  if (err) {
    console.error('Lỗi tạo QR code:', err);
    return;
  }
  
  // Lưu ảnh QR code
  const base64Data = url.replace(/^data:image\/png;base64,/, '');
  fs.writeFileSync('qr.png', base64Data, 'base64');
  console.log('✅ QR code saved as qr.png');
});

// Tạo matrix 41x41 dạng text
QRCode.toString(qrCodeString, {
  type: 'terminal',
  errorCorrectionLevel: 'L',
  version: 6, // Version 6 tạo matrix 41x41
  margin: 0
}, (err, string) => {
  if (err) {
    console.error('Lỗi tạo matrix:', err);
    return;
  }
  console.log('\n📊 Matrix QR Code 41x41:\n');
  console.log(string);
});

// Tạo matrix dạng array 2D [[1,0,1,...],[1,0,1,...],...]
QRCode.toDataURL(qrCodeString, {
  errorCorrectionLevel: 'L',
  version: 6, // Version 6 = 41x41
  margin: 0
}, async (err, url) => {
  if (err) {
    console.error('Lỗi:', err);
    return;
  }
  
  // Decode matrix từ module qrcode
  const qr = await import('qrcode');
  const segments = qr.default.create(qrCodeString, { errorCorrectionLevel: 'L', version: 6 });
  const modules = segments.modules;
  
  // Tạo array 2D theo format [[1,0,1,...],[1,0,1,...],...]
  let matrix = '[';
  for (let y = 0; y < modules.size; y++) {
    matrix += '[';
    for (let x = 0; x < modules.size; x++) {
      const value = modules.get(x, y) ? 1 : 0;
      matrix += value;
      if (x < modules.size - 1) matrix += ',';
    }
    matrix += ']';
    if (y < modules.size - 1) matrix += ',';
  }
  matrix += ']';
  
  // Lưu vào file
  fs.writeFileSync('qr_matrix.txt', matrix);
  console.log('✅ Matrix saved as qr_matrix.txt');
  console.log(`📐 Matrix size: ${modules.size}x${modules.size}`);
  console.log('\n📊 Matrix format: [[1,0,1,...],[1,0,1,...],...]');
});
