<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card budget-card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budgetControl') }}</h3>
        </div>
        <div class="budget-controls">
          <div class="budget-display">{{ formatMoney(safeBudget) }}</div>
          <input
            v-model.number="budgetModel"
            type="range"
            class="budget-slider"
            min="0"
            :max="maxBudget"
            step="500"
            :aria-label="t('restocking.budget')"
          />
          <input
            v-model.number="budgetModel"
            type="number"
            class="budget-input"
            min="0"
            :max="maxBudget"
            step="500"
            :aria-label="t('restocking.budget')"
          />
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.budget') }}</div>
          <div class="stat-value">{{ formatMoney(safeBudget) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.allocated') }}</div>
          <div class="stat-value">{{ formatMoney(allocated) }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.remaining') }}</div>
          <div class="stat-value">{{ formatMoney(remaining) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.orderLeadTime') }}</div>
          <div class="stat-value">{{ t('restocking.days', { count: orderLeadTime }) }}</div>
        </div>
      </div>

      <div v-if="submitError" class="error">{{ submitError }}</div>
      <div v-if="placedOrder" class="success-message">
        <span>{{ t('restocking.orderPlaced', { orderNumber: placedOrder.order_number, date: formatDate(placedOrder.expected_delivery) }) }}</span>
        <router-link to="/orders" class="orders-link">{{ t('restocking.viewOrders') }}</router-link>
      </div>

      <div class="card">
        <div class="card-header header-row">
          <h3 class="card-title">{{ t('restocking.recommendations') }} ({{ recommendations.length }})</h3>
          <button
            type="button"
            class="place-order-btn"
            :disabled="recommendations.length === 0 || submitting"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.submitting') : t('restocking.placeOrder') }}
          </button>
        </div>
        <div v-if="recommendations.length === 0" class="empty-state">
          {{ t('restocking.noRecommendations') }}
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th>{{ t('restocking.table.gap') }}</th>
                <th>{{ t('restocking.table.quantity') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.lineTotal') }}</th>
                <th>{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="rec in recommendations" :key="rec.sku">
                <td><strong>{{ rec.sku }}</strong></td>
                <td>{{ rec.name }}</td>
                <td>
                  <span :class="['badge', rec.trend]">{{ t(`trends.${rec.trend}`) }}</span>
                </td>
                <td>{{ rec.gap }}</td>
                <td><strong>{{ rec.quantity }}</strong></td>
                <td>{{ formatMoney(rec.unit_cost, true) }}</td>
                <td><strong>{{ formatMoney(rec.line_total, true) }}</strong></td>
                <td>{{ t('restocking.days', { count: rec.lead_time_days }) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'

const parseDate = (value) => {
  if (typeof value === 'string') {
    const m = value.match(/^(\d{4})-(\d{2})-(\d{2})$/)
    if (m) return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  }
  return new Date(value)
}

const TREND_ORDER = { increasing: 0, stable: 1, decreasing: 2 }

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, currentLocale } = useI18n()

    const loading = ref(true)
    const error = ref(null)
    const forecasts = ref([])
    const budget = ref(0)
    const submitting = ref(false)
    const submitError = ref(null)
    const placedOrder = ref(null)

    const currencySymbol = computed(() => (currentCurrency.value === 'JPY' ? '¥' : '$'))

    const gapItems = computed(() => {
      return forecasts.value
        .map(f => ({
          sku: f.item_sku,
          name: f.item_name,
          trend: f.trend,
          gap: f.forecasted_demand - f.current_demand,
          unit_cost: Number(f.unit_cost) || 0,
          lead_time_days: Number(f.lead_time_days) || 0
        }))
        .filter(item => item.gap > 0 && item.unit_cost > 0)
        .sort((a, b) => {
          const aInc = a.trend === 'increasing' ? 0 : 1
          const bInc = b.trend === 'increasing' ? 0 : 1
          if (aInc !== bInc) return aInc - bInc
          if (b.gap !== a.gap) return b.gap - a.gap
          return (TREND_ORDER[a.trend] ?? 3) - (TREND_ORDER[b.trend] ?? 3)
        })
    })

    const maxBudget = computed(() => {
      const total = gapItems.value.reduce((sum, i) => sum + i.gap * i.unit_cost, 0)
      return Math.max(500, Math.ceil(total / 500) * 500)
    })

    const safeBudget = computed(() => {
      const b = Number(budget.value)
      if (!Number.isFinite(b) || b <= 0) return 0
      return Math.min(b, maxBudget.value)
    })

    // Clamped model for the slider and number input; user edits dismiss the success banner
    const budgetModel = computed({
      get: () => safeBudget.value,
      set: (value) => {
        const b = Number(value)
        budget.value = Number.isFinite(b) ? Math.min(Math.max(b, 0), maxBudget.value) : 0
        placedOrder.value = null
      }
    })

    // Greedy allocation in integer cents to avoid floating point drift
    const allocation = computed(() => {
      let remainingCents = Math.round(safeBudget.value * 100)
      const budgetCents = remainingCents
      const result = []
      for (const item of gapItems.value) {
        const unitCents = Math.round(item.unit_cost * 100)
        if (unitCents <= 0) continue
        const quantity = Math.min(item.gap, Math.floor(remainingCents / unitCents))
        if (quantity <= 0) continue
        const lineCents = quantity * unitCents
        remainingCents -= lineCents
        result.push({ ...item, quantity, line_total: lineCents / 100 })
      }
      return {
        items: result,
        allocated: (budgetCents - remainingCents) / 100,
        remaining: remainingCents / 100
      }
    })

    const recommendations = computed(() => allocation.value.items)
    const allocated = computed(() => allocation.value.allocated)
    const remaining = computed(() => allocation.value.remaining)
    const orderLeadTime = computed(() =>
      recommendations.value.reduce((max, r) => Math.max(max, r.lead_time_days), 0)
    )

    const formatMoney = (value, decimals = false) => {
      const n = Number(value) || 0
      const hasCents = Math.round(n * 100) % 100 !== 0
      return currencySymbol.value + n.toLocaleString(currentLocale.value === 'ja' ? 'ja-JP' : 'en-US', {
        minimumFractionDigits: decimals || hasCents ? 2 : 0,
        maximumFractionDigits: 2
      })
    }

    const formatDate = (dateString) => {
      const d = parseDate(dateString)
      if (isNaN(d.getTime())) return '-'
      return d.toLocaleDateString(currentLocale.value === 'ja' ? 'ja-JP' : 'en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    }

    const loadForecasts = async () => {
      try {
        loading.value = true
        error.value = null
        forecasts.value = await api.getDemandForecasts()
        budget.value = 0
      } catch (err) {
        error.value = t('restocking.loadError') + ': ' + err.message
      } finally {
        loading.value = false
      }
    }

    const placeOrder = async () => {
      if (recommendations.value.length === 0 || submitting.value) return
      submitting.value = true
      submitError.value = null
      placedOrder.value = null
      try {
        placedOrder.value = await api.createRestockOrder({
          items: recommendations.value.map(r => ({ sku: r.sku, quantity: r.quantity })),
          budget: safeBudget.value
        })
        budget.value = 0
      } catch (err) {
        const detail = err.response?.data?.detail
        submitError.value = t('restocking.submitError') + ': ' + (typeof detail === 'string' ? detail : err.message)
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadForecasts)

    return {
      t,
      loading,
      error,
      budgetModel,
      maxBudget,
      safeBudget,
      recommendations,
      allocated,
      remaining,
      orderLeadTime,
      submitting,
      submitError,
      placedOrder,
      formatMoney,
      formatDate,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-card {
  margin-bottom: 1.5rem;
}

.budget-controls {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 1rem 1.5rem 1.5rem;
  flex-wrap: wrap;
}

.budget-display {
  font-size: 1.75rem;
  font-weight: 700;
  color: #0f172a;
  min-width: 140px;
}

.budget-slider {
  flex: 1;
  min-width: 200px;
  accent-color: #0f172a;
}

.budget-input {
  width: 140px;
  padding: 0.5rem 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 0.938rem;
  color: #0f172a;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.place-order-btn {
  background: #0f172a;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 0.5rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease;
}

.place-order-btn:hover:not(:disabled) {
  background: #1e293b;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.success-message {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  color: #166534;
  padding: 1rem;
  border-radius: 8px;
  margin: 1rem 0;
  font-size: 0.938rem;
}

.orders-link {
  color: #166534;
  font-weight: 600;
  text-decoration: underline;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: #64748b;
  font-size: 0.938rem;
}
</style>
