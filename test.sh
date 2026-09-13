cd frontend
grep -rnE "transition" src/ | grep -v 'colors' | grep -v 'opacity' | grep -v 'transform' | grep -v 'box-shadow' | grep -v 'filter' | grep -v 'border-color' | grep -v 'background-color'
