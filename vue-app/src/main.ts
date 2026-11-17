import { createApp } from 'vue'
import { Quasar, Notify, Dialog } from 'quasar'
import '@quasar/extras/material-icons/material-icons.css'
import 'quasar/src/css/index.sass'
import './tokens.css'
import App from './App.vue'
import { router } from './router'
import { initLang } from './i18n'
import { setTheme, theme } from './theme'

createApp(App)
  .use(Quasar, { plugins: { Notify, Dialog } })
  .use(router)
  .mount('#app')

initLang()
setTheme(theme.value)
