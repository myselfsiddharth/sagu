// A tiny in-browser SIMULATION of Sagu's games, so you can try the commands. The real bot is the Python program.
(function () {
  var box = document.getElementById('chat'), form = document.getElementById('send'), input = document.getElementById('msg');
  if (!box) return;
  var P = '\u{1F335} ', game = null, deal = null, ins = [], scores = {};
  var pick = function (a) { return a[Math.floor(Math.random() * a.length)]; };
  function add(text, who, label) {
    var d = document.createElement('div'); d.className = 'msg ' + who;
    if (label) { var b = document.createElement('b'); b.textContent = label; d.appendChild(b); }
    d.appendChild(document.createTextNode(text)); box.appendChild(d); box.scrollTop = box.scrollHeight;
  }
  function sagu(t) { setTimeout(function () { add(P + t, 'them', 'Sagu'); }, 350); }
  var BALL = ['Yes. Obviously.', 'Ask again after some water.', 'Absolutely not.', 'My spines say no.', 'Do it. Worry later.', 'Signs point to yes.', 'Doubtful. Cacti are realists.'];
  var TRIVIA = [['How often does a desert cactus need watering?', ['Every day', 'Every few weeks', 'Never, ever'], 2], ['Which planet is closest to the sun?', ['Venus', 'Mercury', 'Mars'], 2], ['What is the capital of Japan?', ['Kyoto', 'Osaka', 'Tokyo'], 3]];
  var WORDS = ['cactus', 'desert', 'sunrise', 'picnic', 'lantern'];
  function mask(g) { return g.word.split('').map(function (c) { return g.seen.indexOf(c) > -1 ? c : '_'; }).join(' '); }
  function handle(raw) {
    var t = raw.trim(), m = /^sagu\b[\s,:!.-]*(.*)$/i.exec(t);
    if (!m) { if (deal && /^(in|i'?m in|down)\W*$/i.test(t)) { ins.push('You'); sagu(ins.length < 2 ? "Got you. That's 1. I need one more to make it a plan." : 'That is ' + ins.length + ' for ' + deal + '. Proposed time: Sunday 6:30pm.'); } return; }
    var rest = m[1].trim(), w = rest.split(/\s+/), head = w[0].toLowerCase().replace(/[?!.,:]+$/, ''), arg = w.slice(1).join(' ');
    if (/^\d{1,3}$/.test(head)) {
      var n = +head; if (!game) return;
      if (game.k === 'guess') { game.t++; if (n === game.n) { scores.You = (scores.You || 0) + 1; sagu('You got it: ' + n + ' in ' + game.t + ' tries. +1 point.'); game = null; } else sagu(n + ' is too ' + (n < game.n ? 'low' : 'high') + '.'); }
      else if (game.k === 'trivia') { if (n === game.a) { scores.You = (scores.You || 0) + 1; sagu('Right: ' + game.o[n - 1] + '. +1 point.'); } else sagu('Not quite. It was ' + game.a + ', ' + game.o[game.a - 1] + '.'); game = null; }
      return;
    }
    switch (head) {
      case 'help': case 'games': sagu('Try: sagu trivia, sagu guess, sagu hangman, sagu wyr, sagu 8ball <q>, sagu pick x, y, z, sagu flip, sagu dice, sagu deal: <deal>, sagu scores'); break;
      case 'flip': sagu(pick(['Heads.', 'Tails.'])); break;
      case 'dice': case 'roll': sagu('Rolled 1d6: ' + (1 + Math.floor(Math.random() * 6))); break;
      case '8ball': case 'ask': sagu(arg ? pick(BALL) : 'Ask me something first: sagu 8ball will we win?'); break;
      case 'pick': var o = arg.split(/,|\bor\b/).map(function (s) { return s.trim(); }).filter(Boolean); sagu(o.length < 2 ? 'Give me at least two options: sagu pick pizza, tacos, sushi' : 'I pick: ' + pick(o) + '.'); break;
      case 'guess': game = { k: 'guess', n: 1 + Math.floor(Math.random() * 50), t: 0 }; sagu('I am thinking of a number from 1 to 50. Guess with "sagu 25".'); break;
      case 'trivia': var q = pick(TRIVIA); game = { k: 'trivia', o: q[1], a: q[2] }; sagu('Trivia: ' + q[0] + '\n' + q[1].map(function (x, i) { return (i + 1) + '. ' + x; }).join('\n') + '\nAnswer with "sagu 1", "sagu 2" or "sagu 3".'); break;
      case 'hangman': game = { k: 'hang', word: pick(WORDS), seen: [], wrong: 0 }; sagu('Hangman! ' + mask(game) + '\nGuess with "sagu letter e". 6 misses and the cactus wilts.'); break;
      case 'letter': if (!game || game.k !== 'hang') { sagu('No hangman going. Start one with "sagu hangman".'); break; }
        var c = arg.toLowerCase(); if (c.length !== 1) { sagu('One letter at a time: sagu letter e'); break; }
        if (game.seen.indexOf(c) > -1) { sagu('Already tried ' + c + '. ' + mask(game)); break; }
        game.seen.push(c);
        if (game.word.indexOf(c) > -1) { if (game.word.split('').every(function (x) { return game.seen.indexOf(x) > -1; })) { scores.You = (scores.You || 0) + 2; sagu('You finished it: ' + game.word + '. +2 points.'); game = null; } else sagu('Yes. ' + mask(game)); }
        else { game.wrong++; if (game.wrong >= 6) { sagu('The cactus wilted. The word was ' + game.word + '.'); game = null; } else sagu('Nope. ' + (6 - game.wrong) + ' misses left. ' + mask(game)); } break;
      case 'wyr': game = { k: 'wyr' }; sagu('Would you rather...\nA. have summer all year\nB. have autumn all year\nVote with "sagu a" or "sagu b".'); break;
      case 'a': case 'b': if (game && game.k === 'wyr') sagu('You picked ' + head.toUpperCase() + '. Your friends will judge you.'); break;
      case 'scores': sagu(Object.keys(scores).length ? 'Scoreboard:\n' + Object.keys(scores).map(function (k) { return k + ' - ' + scores[k]; }).join('\n') : 'No points yet. Try "sagu trivia".'); break;
      case 'stop': game = null; sagu('Game over.'); break;
      case 'deal:': case 'deal': if (!arg.replace(/^[:\-\s]+/, '')) { sagu('I need a bit more than that. Try: sagu deal: 2-for-1 tacos till Friday'); break; }
        deal = arg.replace(/^[:\-\s]+/, ''); ins = []; sagu('On it: ' + deal + '. Who is in? Reply "in".'); break;
      case 'on': sagu("Sagu here. I'm a small cactus. \"sagu help\" for the rest."); break;
      default: sagu('Yes? "sagu help" lists what I do.');
    }
  }
  form.addEventListener('submit', function (e) { e.preventDefault(); var v = input.value.trim(); if (!v) return; add(v, 'me', 'You'); input.value = ''; handle(v); });
  document.querySelectorAll('[data-say]').forEach(function (b) { b.addEventListener('click', function () { add(b.dataset.say, 'me', 'You'); handle(b.dataset.say); }); });
  add('sagu on', 'me', 'You (host)'); sagu("Sagu here. I'm a small cactus. This is a browser simulation: try the buttons below.");
})();
