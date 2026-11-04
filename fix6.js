const fs = require('fs');
const content = fs.readFileSync('frontend/src/app/apollo/page.tsx', 'utf8');
const replaced = content.replace(
  '<div className="flex flex-wrap items-center gap-2 px-3 py-1.5 sm:px-4">',
  '<div className="min-h-0">\n          <div className="flex flex-wrap items-center gap-2 px-3 py-1.5 sm:px-4">'
).replace(
  '            </span>\n          )}\n        </div>\n      </div>',
  '            </span>\n          )}\n          </div>\n        </div>\n      </div>'
);
fs.writeFileSync('frontend/src/app/apollo/page.tsx', replaced);
