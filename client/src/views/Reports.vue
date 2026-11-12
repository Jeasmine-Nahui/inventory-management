<template>
  <div class="reports">
    <div class="page-header">
      <h2>{{ t('reports.title') }}</h2>
      <p>{{ t('reports.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('reports.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <!-- Quarterly Performance -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.quarterly.title') }}</h3>
        </div>
        <div v-if="quarterlyData.length === 0" class="no-data">{{ t('reports.empty') }}</div>
        <div v-else class="table-container">
          <table class="reports-table">
            <thead>
              <tr>
                <th>{{ t('reports.quarterly.quarter') }}</th>
                <th>{{ t('reports.quarterly.totalOrders') }}</th>
                <th>{{ t('reports.quarterly.totalRevenue') }}</th>
                <th>{{ t('reports.quarterly.avgOrderValue') }}</th>
                <th>{{ t('reports.quarterly.fulfillmentRate') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="q in quarterlyData" :key="q.quarter">
                <td><strong>{{ q.quarter }}</strong></td>
                <td>{{ formatCount(q.total_orders) }}</td>
                <td>{{ money(q.total_revenue) }}</td>
                <td>{{ money(q.avg_order_value) }}</td>
                <td>
                  <span :class="['badge', getFulfillmentClass(q.fulfillment_rate)]">
                    {{ q.fulfillment_rate }}%
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Monthly Trends Chart -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.trend.title') }}</h3>
        </div>
        <div v-if="monthlyData.length === 0" class="no-data">{{ t('reports.empty') }}</div>
        <div v-else class="chart-container">
          <div class="bar-chart">
            <div v-for="month in monthlyData" :key="month.month" class="bar-wrapper">
              <div class="bar-container">
                <div
                  class="bar"
                  :style="{ height: getBarHeight(month.revenue) + 'px' }"
                  :title="money(month.revenue)"
                ></div>
              </div>
              <div class="bar-label">{{ formatMonth(month.month) }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Month-over-Month Comparison -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.mom.title') }}</h3>
        </div>
        <div v-if="monthlyData.length === 0" class="no-data">{{ t('reports.empty') }}</div>
        <div v-else class="table-container">
          <table class="reports-table">
            <thead>
              <tr>
                <th>{{ t('reports.mom.month') }}</th>
                <th>{{ t('reports.mom.orders') }}</th>
                <th>{{ t('reports.mom.revenue') }}</th>
                <th>{{ t('reports.mom.change') }}</th>
                <th>{{ t('reports.mom.growthRate') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(month, index) in monthlyData" :key="month.month">
                <td><strong>{{ formatMonth(month.month) }}</strong></td>
                <td>{{ formatCount(month.order_count) }}</td>
                <td>{{ money(month.revenue) }}</td>
                <td>
                  <span v-if="index > 0" :class="getChangeClass(month.revenue, monthlyData[index - 1].revenue)">
                    {{ getChangeValue(month.revenue, monthlyData[index - 1].revenue) }}
                  </span>
                  <span v-else>-</span>
                </td>
                <td>
                  <span v-if="index > 0" :class="getChangeClass(month.revenue, monthlyData[index - 1].revenue)">
                    {{ getGrowthRate(month.revenue, monthlyData[index - 1].revenue) }}
                  </span>
                  <span v-else>-</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Summary Stats -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.stats.totalRevenue') }}</div>
          <div class="stat-value">{{ money(totalRevenue) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.stats.avgMonthlyRevenue') }}</div>
          <div class="stat-value">{{ money(avgMonthlyRevenue) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.stats.totalOrders') }}</div>
          <div class="stat-value">{{ formatCount(totalOrders) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.stats.bestQuarter') }}</div>
          <div class="stat-value">{{ bestQuarter }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'
import { formatCurrency } from '../utils/currency'

export default {
  name: 'Reports',
  setup() {
    const { t, currentLocale, currentCurrency } = useI18n()
    const {
      selectedPeriod,
      selectedLocation,
      selectedCategory,
      selectedStatus,
      getCurrentFilters
    } = useFilters()

    const loading = ref(true)
    const error = ref(null)
    const quarterlyData = ref([])
    const monthlyData = ref([])

    const localeTag = computed(() => (currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'))

    const loadData = async () => {
      try {
        loading.value = true
        error.value = null
        const filters = getCurrentFilters()
        const [quarterly, monthly] = await Promise.all([
          api.getQuarterlyReports(filters),
          api.getMonthlyTrends(filters)
        ])
        quarterlyData.value = Array.isArray(quarterly) ? quarterly : []
        monthlyData.value = Array.isArray(monthly) ? monthly : []
      } catch (err) {
        error.value = t('reports.loadError') + ': ' + err.message
        console.error('Failed to load reports:', err)
      } finally {
        loading.value = false
      }
    }

    watch([selectedPeriod, selectedLocation, selectedCategory, selectedStatus], () => {
      loadData()
    })

    onMounted(loadData)

    // Derived data
    const totalRevenue = computed(() =>
      monthlyData.value.reduce((sum, m) => sum + (Number(m.revenue) || 0), 0)
    )

    const avgMonthlyRevenue = computed(() =>
      monthlyData.value.length > 0 ? totalRevenue.value / monthlyData.value.length : 0
    )

    const totalOrders = computed(() =>
      monthlyData.value.reduce((sum, m) => sum + (Number(m.order_count) || 0), 0)
    )

    const bestQuarter = computed(() => {
      let best = null
      for (const q of quarterlyData.value) {
        if (!best || (Number(q.total_revenue) || 0) > (Number(best.total_revenue) || 0)) {
          best = q
        }
      }
      return best && best.quarter ? best.quarter : '-'
    })

    const maxRevenue = computed(() =>
      monthlyData.value.reduce((max, m) => Math.max(max, Number(m.revenue) || 0), 0)
    )

    // Formatting helpers
    const money = (amount) => formatCurrency(Number(amount) || 0, currentCurrency.value)

    const formatCount = (n) => (Number(n) || 0).toLocaleString(localeTag.value)

    const formatMonth = (monthStr) => {
      if (typeof monthStr !== 'string' || !/^\d{4}-(0[1-9]|1[0-2])$/.test(monthStr)) return '-'
      const [year, month] = monthStr.split('-').map(Number)
      const date = new Date(year, month - 1, 1)
      if (isNaN(date.getTime())) return '-'
      return date.toLocaleDateString(localeTag.value, { year: 'numeric', month: 'short' })
    }

    const getBarHeight = (revenue) => {
      if (maxRevenue.value === 0) return 0
      return ((Number(revenue) || 0) / maxRevenue.value) * 200
    }

    const getFulfillmentClass = (rate) => {
      if (rate >= 90) return 'success'
      if (rate >= 75) return 'warning'
      return 'danger'
    }

    const getChangeValue = (current, previous) => {
      const change = (Number(current) || 0) - (Number(previous) || 0)
      if (change > 0) return '+' + money(change)
      if (change < 0) return '-' + money(Math.abs(change))
      return money(0)
    }

    const getChangeClass = (current, previous) => {
      const change = (Number(current) || 0) - (Number(previous) || 0)
      if (change > 0) return 'positive-change'
      if (change < 0) return 'negative-change'
      return ''
    }

    const getGrowthRate = (current, previous) => {
      const prev = Number(previous) || 0
      if (prev === 0) return t('reports.notAvailable')
      const rate = (((Number(current) || 0) - prev) / prev) * 100
      return (rate > 0 ? '+' : '') + rate.toFixed(1) + '%'
    }

    return {
      t,
      loading,
      error,
      quarterlyData,
      monthlyData,
      totalRevenue,
      avgMonthlyRevenue,
      totalOrders,
      bestQuarter,
      money,
      formatCount,
      formatMonth,
      getBarHeight,
      getFulfillmentClass,
      getChangeValue,
      getChangeClass,
      getGrowthRate
    }
  }
}
</script>

<style scoped>
.reports {
  padding: 0;
}

.chart-container {
  padding: 2rem 1rem;
  min-height: 300px;
}

.bar-chart {
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  height: 250px;
  gap: 0.5rem;
}

.bar-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  max-width: 80px;
}

.bar-container {
  height: 200px;
  display: flex;
  align-items: flex-end;
  width: 100%;
}

.bar {
  width: 100%;
  background: #64748b;
  border-radius: 4px 4px 0 0;
  transition: background 0.3s;
  cursor: pointer;
}

.bar:hover {
  background: #475569;
}

.bar-label {
  font-size: 0.75rem;
  color: #64748b;
  text-align: center;
  transform: rotate(-45deg);
  white-space: nowrap;
  margin-top: 1.5rem;
}

.no-data {
  padding: 2rem;
  text-align: center;
  color: #94a3b8;
  font-size: 0.875rem;
}

.stats-grid {
  margin-top: 1.5rem;
}

.positive-change {
  color: #16a34a;
  font-weight: 600;
}

.negative-change {
  color: #dc2626;
  font-weight: 600;
}
</style>
