import { createApp } from 'vue'
import { Quasar, Notify, Dialog } from 'quasar'
import quasarLang from 'quasar/lang/uk'
import '@quasar/extras/material-icons/material-icons.css'
import 'quasar/src/css/index.sass'
import './tokens.css'
import App from './App.vue'
import { router } from './router'

createApp(App)
  .use(Quasar, { plugins: { Notify, Dialog }, lang: quasarLang, config: { brand: { primary: '#3651E6', positive: '#16A34A', negative: '#DC2626' } } })
  .use(router)
  .mount('#app')
