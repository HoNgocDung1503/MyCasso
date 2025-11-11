import fs from 'fs';

const response = await fetch('https://api.vietqr.io/v2/generate', {
  method: 'POST',
  headers: {
    'x-api-key': 'we-l0v3-v1et-qr',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    accountNo: 113366668888,
    accountName: "QUY VAC XIN PHONG CHONG COVID",
    acqId: 970415,
    amount: 79000,
    addInfo: "Ung Ho Quy Vac Xin",
    format: "text",
    template: "compact"
  })
});

const data = await response.json();
console.log(data);

const base64Data = data.data.qrDataURL.replace(/^data:image\/png;base64,/, '');
fs.writeFileSync('qr.png', base64Data, 'base64');
console.log('✅ QR code saved as qr.png');
