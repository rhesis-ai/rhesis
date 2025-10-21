# Test Generation Interface - Implementation Guide

## 📋 Quick Start

You've been provided with a comprehensive implementation plan to replace the current test generation interface. Here's what you have:

### 📁 Documentation Files

1. **IMPLEMENTATION_PLAN.md** - Detailed technical implementation plan
   - 7 phases of development
   - Component breakdown
   - API integration strategy
   - Timeline and dependencies

2. **IMPLEMENTATION_SUMMARY.md** - Executive summary
   - Quick overview of changes
   - Current vs new flow comparison
   - Technology stack
   - 3-week timeline
   - Key decisions needed

3. **COMPONENT_MAPPING.md** - Mockup to MUI conversion guide
   - Element-by-element mapping
   - CSS conversion (Tailwind → MUI sx)
   - State management patterns
   - Complete styling guide

4. **FLOW_DIAGRAM.md** - Visual flow diagrams
   - User journey maps
   - Component hierarchy
   - Data flow diagrams
   - API call sequences
   - State transitions

## 🎯 What's Being Built

### Current State
A 4-step stepper interface for test generation with basic configuration, document upload, sample review, and confirmation.

### New State
A multi-screen, chat-enhanced interface with:
- Landing page with 3 options (AI, Manual, Templates)
- Template library (12 pre-configured test suites)
- 2-panel generation interface (config + live preview)
- Chat-based refinement
- Test set sizing with cost estimates
- Reusable test set naming

## 🏗️ Architecture Overview

```
/tests/new-generated/
├── page.tsx (updated)
└── components/
    ├── TestGenerationFlow.tsx (main orchestrator)
    ├── LandingScreen.tsx
    ├── TestInputScreen.tsx
    ├── TestGenerationInterface.tsx
    ├── TestConfigurationConfirmation.tsx
    └── shared/
        ├── ChipGroup.tsx
        ├── DocumentUpload.tsx
        ├── TestSampleCard.tsx
        ├── TestSetSizeSelector.tsx
        └── types.ts
```

## 📊 Key Metrics

- **Total Components**: 9 (5 screens + 4 shared)
- **Estimated LOC**: ~1,800 lines
- **Code Reuse**: ~40% from existing implementation
- **New Dependencies**: 0 (uses existing MUI + Lucide)
- **Development Time**: 3 weeks
- **Breaking Changes**: None (frontend-only)

## ✅ Implementation Checklist

### Week 1: Development
- [ ] Day 1: Create component structure, type definitions
- [ ] Days 2-4: Build all components (Landing, Input, Interface, Confirmation, Shared)
- [ ] Day 5: Create TestGenerationFlow orchestrator
- [ ] Day 6: API integration and data mapping
- [ ] Day 7: Integration testing
- [ ] Days 8-9: Polish, animations, documentation

### Week 2: QA & Refinement
- [ ] Days 1-2: Internal QA testing
- [ ] Days 3-4: Bug fixes and improvements
- [ ] Day 5: Deploy to staging

### Week 3: Deployment
- [ ] Day 1: Deploy to production
- [ ] Days 2-5: Monitor, fix issues, gather feedback

## 🚀 Getting Started

### Step 1: Review Documentation
Read the implementation documents in this order:
1. IMPLEMENTATION_SUMMARY.md (10 min) - Get the big picture
2. FLOW_DIAGRAM.md (15 min) - Understand the user journey
3. COMPONENT_MAPPING.md (30 min) - See mockup → code mappings
4. IMPLEMENTATION_PLAN.md (60 min) - Detailed technical specs

### Step 2: Set Up Development Environment
```bash
# Create feature branch
git checkout -b feature/new-test-generation-ui

# Navigate to frontend
cd apps/frontend

# Start dev server
npm run dev
```

### Step 3: Create Component Files
```bash
cd src/app/(protected)/tests/new-generated/components

# Create main components
touch TestGenerationFlow.tsx
touch LandingScreen.tsx
touch TestInputScreen.tsx
touch TestGenerationInterface.tsx
touch TestConfigurationConfirmation.tsx

# Create shared components
mkdir -p shared
cd shared
touch ChipGroup.tsx
touch DocumentUpload.tsx
touch TestSampleCard.tsx
touch TestSetSizeSelector.tsx
touch types.ts
```

### Step 4: Start Implementing
Begin with Phase 1 from IMPLEMENTATION_PLAN.md:
1. Set up types in `shared/types.ts`
2. Build simplest components first (ChipGroup, TestSetSizeSelector)
3. Build screen components
4. Create orchestrator
5. Integrate with existing APIs

## 🔧 Technical Stack

### Already Available
- ✅ Material-UI v6 (UI components)
- ✅ Lucide React (icons)
- ✅ React 19 (framework)
- ✅ TypeScript (type safety)
- ✅ Next.js 15 (routing, SSR)
- ✅ ApiClientFactory (backend integration)

### No New Dependencies Needed!

## 📝 Key Design Decisions

### 1. UI Library: MUI (Not shadcn/ui)
**Reason**: Project already uses MUI, no need to add shadcn/ui

### 2. State Management: Local State + Callbacks
**Reason**: Flow is self-contained, no need for global state

### 3. Migration Strategy: Hard Cutover
**Reason**: Clean transition, easier to maintain

### 4. Code Organization: Component per Screen
**Reason**: Better separation of concerns, easier testing

### 5. API Integration: Reuse Existing
**Reason**: No backend changes needed, proven patterns

## ⚠️ Important Notes

### Feature Parity Required
The new interface must maintain ALL current features:
- ✅ Project selection
- ✅ Behavior/purpose selection
- ✅ Document upload with processing
- ✅ Sample generation and preview
- ✅ Sample rating and feedback
- ✅ Sample regeneration
- ✅ Final test set generation

### New Features to Add
- ✨ Template library
- ✨ Chat-based refinement
- ✨ Test set sizing
- ✨ Test set naming
- ✨ Improved sample UI
- ✨ Context picker

### What NOT to Change
- ❌ Backend APIs
- ❌ Authentication flow
- ❌ Data models
- ❌ Test generation logic

## 🐛 Testing Strategy

### Unit Tests
```typescript
// Example: ChipGroup.test.tsx
describe('ChipGroup', () => {
  it('renders chips correctly', () => {});
  it('toggles chip on click', () => {});
  it('applies correct color variant', () => {});
});
```

### Integration Tests
```typescript
// Example: TestGenerationFlow.test.tsx
describe('TestGenerationFlow', () => {
  it('navigates through full flow', () => {});
  it('calls API at correct times', () => {});
  it('handles errors gracefully', () => {});
});
```

### E2E Tests
```typescript
// Example: test-generation.e2e.ts
describe('Test Generation E2E', () => {
  it('completes full generation flow', () => {});
  it('uploads documents successfully', () => {});
  it('generates and rates samples', () => {});
});
```

## 📈 Success Criteria

### User Experience
- ⏱️ Time to complete flow: <50% of current
- 😊 User satisfaction: >4/5 stars
- ✅ Completion rate: >90%

### Technical
- 🐛 Error rate: <2%
- ⚡ API response time: <2s
- 📱 Mobile responsive: 100%

### Business
- 📊 Test sets generated: +20%
- 🎯 Template adoption: >50%
- 🔄 User retention: +15%

## 🤔 Open Questions

Please decide on these before implementation:

1. **Project Selection Location**
   - Option A: Separate dropdown at top
   - Option B: Integrate into configuration panel
   - **Recommendation**: Option A

2. **Template Defaults**
   - Which 12 templates to include?
   - **Recommendation**: Use mockup list

3. **Test Set Pricing**
   - Small: $12 for 25-50 tests
   - Medium: $29 for 75-150 tests
   - Large: $67 for 200+ tests
   - **Recommendation**: Confirm with backend team

4. **Feature Flag**
   - Gradual rollout or big bang?
   - **Recommendation**: Big bang with staging testing

## 🔗 Related Files

### Current Implementation
- `apps/frontend/src/app/(protected)/tests/new-generated/page.tsx`
- `apps/frontend/src/app/(protected)/tests/new-generated/components/GenerateTestsStepper.tsx`

### API Clients
- `apps/frontend/src/utils/api-client/client-factory.ts`
- `apps/frontend/src/utils/api-client/services-client.ts`
- `apps/frontend/src/utils/api-client/test-sets-client.ts`

### Interfaces
- `apps/frontend/src/utils/api-client/interfaces/test-set.ts`
- `apps/frontend/src/utils/api-client/interfaces/documents.ts`

## 📞 Support

If you have questions during implementation:

1. **Clarification on Design**: Refer to COMPONENT_MAPPING.md
2. **Clarification on Flow**: Refer to FLOW_DIAGRAM.md
3. **Clarification on Architecture**: Refer to IMPLEMENTATION_PLAN.md
4. **API Integration**: Check existing `GenerateTestsStepper.tsx` for patterns

## 🎉 Next Steps

1. ✅ Review all documentation (you're here!)
2. ⬜ Get stakeholder approval on approach
3. ⬜ Create feature branch
4. ⬜ Set up component structure
5. ⬜ Begin Phase 1 implementation
6. ⬜ Daily commits and progress updates
7. ⬜ Weekly demos to stakeholders

---

## 📄 Quick Reference

| Document | Purpose | Read Time |
|----------|---------|-----------|
| README_IMPLEMENTATION.md | This file - overview | 10 min |
| IMPLEMENTATION_SUMMARY.md | Executive summary | 10 min |
| FLOW_DIAGRAM.md | Visual diagrams | 15 min |
| COMPONENT_MAPPING.md | Code conversion guide | 30 min |
| IMPLEMENTATION_PLAN.md | Full technical specs | 60 min |

**Total Reading Time**: ~2 hours

---

**Ready to build? Let's do this! 🚀**

Start with Phase 1 from IMPLEMENTATION_PLAN.md and work your way through each component systematically. Remember: you're not starting from scratch - you're evolving an existing feature with a better UX!
