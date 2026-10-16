import type { Theme } from 'vitepress'
import DefaultTheme from 'vitepress/theme-without-fonts'
import SuiteOverview from './SuiteOverview.vue'
import './style.css'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('SuiteOverview', SuiteOverview)
  }
} satisfies Theme
