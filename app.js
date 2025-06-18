// Initialize Telegram WebApp
const tg = window.Telegram.WebApp;
tg.expand();

// State
let deliveryType = 'delivery';
let selectedTip = 0;

// Toggles
const delivBtn = document.getElementById('delivBtn');
const pickupBtn = document.getElementById('pickupBtn');
delivBtn.onclick = () => toggle('delivery');
pickupBtn.onclick = () => toggle('pickup');
function toggle(type) {
  deliveryType = type;
  delivBtn.classList.toggle('active', type==='delivery');
  pickupBtn.classList.toggle('active', type==='pickup');
}

// Tip buttons
document.querySelectorAll('.tip-buttons button').forEach(btn => {
  btn.onclick = () => {
    selectedTip = parseInt(btn.dataset.tip);
    document.querySelectorAll('.tip-buttons button')
      .forEach(b => b.classList.toggle('selected', b===btn));
  };
});

// Continue → payload
document.getElementById('continueBtn').onclick = () => {
  const form = document.getElementById('orderForm');
  if (!form.reportValidity()) return;
  const payload = {
    deliveryType,
    address: document.getElementById('address').value,
    apt: document.getElementById('apt').value,
    instructions: document.getElementById('instructions').value,
    groupLink: document.getElementById('groupLink').value,
    name: document.getElementById('name').value,
    phone: document.getElementById('phone').value,
    paymentMethod: document.getElementById('paymentMethod').value,
    tip: selectedTip
  };
  // Send to bot
  tg.sendData(JSON.stringify(payload));
};